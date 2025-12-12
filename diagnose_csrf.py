#!/usr/bin/env python3
"""
em caso de erro CSRF, rode local para diagnosticar o que está ocorrendo no host vps:
    python diagnose_csrf.py --settings votebem.settings.production --base-url https://votebem.online 

Purpose:
- Diagnose Django CSRF and proxy-related misconfigurations and template issues
  in the current VoteBem project. Writes a detailed report to
  `docs/diagnostics_csrf_report.txt` and prints a concise summary.

Key checks (settings):
- ALLOWED_HOSTS
- CSRF_TRUSTED_ORIGINS (must include full scheme, e.g., https://domain)
- SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE / CSRF_COOKIE_SAMESITE
- CSRF_COOKIE_DOMAIN
- SECURE_PROXY_SSL_HEADER / USE_X_FORWARDED_HOST
- SECURE_SSL_REDIRECT
- Presence of `django.middleware.csrf.CsrfViewMiddleware`

Key checks (templates):
- Scan project-level `templates/` and app templates for `<form method="post">`
  missing `{% csrf_token %}`.
- Scan for inline `fetch` or `axios` POST/PUT/DELETE calls missing
  `X-CSRFToken` header.

Key checks (code):
- Flag any usage of `@csrf_exempt` (may be legitimate but risky).

Optional online probe:
- If `--base-url` is provided (e.g., `http://127.0.0.1:8001/` for the
  container port mapping), perform GET requests to a few endpoints (such as
  `/users/login/`) and verify the rendered CSRF input (`name="csrfmiddlewaretoken"`).

Run examples:
- `python diagnose_csrf.py`
- `python diagnose_csrf.py --base-url http://127.0.0.1:8001/`
- `python diagnose_csrf.py --settings votebem.settings.production`

Notes:
- This script initializes Django to inspect live settings. Ensure dependencies
  are installed and the working directory is the project root.
"""

import os
import re
import sys
from datetime import datetime
from typing import Tuple, Dict, List, Optional


# -----------------------------
# Configuration & Environment
# -----------------------------
def _is_project_root(path: str) -> bool:
    """Heuristically decide if `path` is the Django project root.

    We expect `manage.py` and the `votebem/` package to exist.
    """
    try:
        return (
            os.path.isfile(os.path.join(path, "manage.py"))
            and os.path.isdir(os.path.join(path, "votebem"))
        )
    except Exception:
        return False


def _detect_project_root(script_path: str) -> str:
    """Detect the project root robustly when running inside Docker at `/app`.

    Tries the script directory, its parent, and grandparent. Falls back to the
    script directory if nothing matches.
    """
    script_dir = os.path.dirname(script_path)
    candidates = [
        script_dir,
        os.path.dirname(script_dir),
        os.path.dirname(os.path.dirname(script_dir)),
    ]
    for cand in candidates:
        if _is_project_root(cand):
            return cand
    return script_dir


def project_paths() -> Tuple[str, str, str, List[str], str, str]:
    """
    Compute important paths relative to this script for the VoteBem project.

    Returns:
        - project_root: repository root
        - settings_module: DJANGO_SETTINGS_MODULE to use
        - templates_root: root-level templates directory
        - app_roots: list of app directories to scan (for templates and code)
        - report_path: path to write the text report
        - docs_dir: directory to save diagnostic artifacts
    """
    script_path = os.path.abspath(__file__)
    project_root = _detect_project_root(script_path)

    # Prefer environment variable if set; else allow CLI override; fallback to
    # the project's default used in manage.py.
    env_settings = os.environ.get("DJANGO_SETTINGS_MODULE")
    settings_module = env_settings or "votebem.settings.production"

    templates_root = os.path.join(project_root, "templates")
    app_roots = [
        os.path.join(project_root, "voting"),
        os.path.join(project_root, "users"),
        os.path.join(project_root, "polls"),
        os.path.join(project_root, "home"),
    ]
    docs_dir = os.path.join(project_root, "docs")
    report_path = os.path.join(docs_dir, "diagnostics_csrf_report.txt")
    return project_root, settings_module, templates_root, app_roots, report_path, docs_dir


def init_django(project_root: str, settings_module: str) -> Tuple[bool, Optional[str]]:
    """
    Initialize Django so we can read `django.conf.settings` for this project.
    """
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Force override to respect CLI '--settings' even if the environment
    # already defines DJANGO_SETTINGS_MODULE (e.g., inside Docker).
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    try:
        import django
        django.setup()
    except Exception as exc:
        return False, f"Failed to initialize Django: {exc}"
    return True, None


# -----------------------------
# Settings Diagnostics
# -----------------------------
def collect_settings_diagnostics() -> Dict[str, object]:
    """
    Gather key CSRF/proxy/security settings from the active Django settings.
    """
    from django.conf import settings
    data = {
        "DJANGO_SETTINGS_MODULE": os.environ.get("DJANGO_SETTINGS_MODULE"),
        "DEBUG": getattr(settings, "DEBUG", None),
        "ALLOWED_HOSTS": getattr(settings, "ALLOWED_HOSTS", []),
        "CSRF_TRUSTED_ORIGINS": getattr(settings, "CSRF_TRUSTED_ORIGINS", []),
        "SESSION_COOKIE_SECURE": getattr(settings, "SESSION_COOKIE_SECURE", None),
        "CSRF_COOKIE_SECURE": getattr(settings, "CSRF_COOKIE_SECURE", None),
        "CSRF_COOKIE_SAMESITE": getattr(settings, "CSRF_COOKIE_SAMESITE", None),
        "CSRF_COOKIE_DOMAIN": getattr(settings, "CSRF_COOKIE_DOMAIN", None),
        "SECURE_PROXY_SSL_HEADER": getattr(settings, "SECURE_PROXY_SSL_HEADER", None),
        "USE_X_FORWARDED_HOST": getattr(settings, "USE_X_FORWARDED_HOST", None),
        "SECURE_SSL_REDIRECT": getattr(settings, "SECURE_SSL_REDIRECT", None),
        "MIDDLEWARE": list(getattr(settings, "MIDDLEWARE", [])),
    }
    data["HAS_CSRF_MIDDLEWARE"] = any(
        (mw or "").strip() == "django.middleware.csrf.CsrfViewMiddleware" for mw in data["MIDDLEWARE"]
    )
    return data


# -----------------------------
# Template & JS Scanning
# -----------------------------
FORM_OPEN_RE = re.compile(r"<form[^>]*method=['\"]post['\"][^>]*>", re.IGNORECASE)
FORM_CLOSE_RE = re.compile(r"</form>", re.IGNORECASE)
FETCH_POST_RE = re.compile(r"fetch\s*\(.*?\{.*?method\s*:\s*['\"](POST|PUT|DELETE)['\"].*?\}.*?\)", re.IGNORECASE | re.DOTALL)
AXIOS_POST_RE = re.compile(r"axios\.[a-zA-Z]+\s*\(.*?\)", re.IGNORECASE | re.DOTALL)


def find_forms_missing_csrf(file_path: str) -> List[str]:
    """
    Return snippets for `<form method="post">` blocks lacking `{% csrf_token %}`
    in the given HTML file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return []

    missing = []
    pos = 0
    while True:
        m_open = FORM_OPEN_RE.search(html, pos)
        if not m_open:
            break
        m_close = FORM_CLOSE_RE.search(html, m_open.end())
        if not m_close:
            # Unclosed form; flag but continue
            snippet = html[m_open.start(): m_open.end() + 200]
            missing.append(snippet)
            pos = m_open.end()
            continue
        snippet = html[m_open.start(): m_close.end()]
        if "csrf_token" not in snippet:
            missing.append(snippet)
        pos = m_close.end()
    return missing


def find_js_calls_missing_csrf(file_path: str) -> List[str]:
    """
    Scan HTML for inline JS fetch/axios calls performing write operations
    where an `X-CSRFToken` header is missing.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return []

    findings = []
    for m in FETCH_POST_RE.finditer(html):
        snippet = m.group(0)
        if "X-CSRFToken" not in snippet:
            findings.append(snippet)

    # Simple heuristic for axios: flag if no 'X-CSRFToken' appears nearby.
    for m in AXIOS_POST_RE.finditer(html):
        snippet = m.group(0)
        if re.search(r"axios\.(post|put|delete)", snippet, re.IGNORECASE):
            start = max(0, m.start() - 300)
            end = min(len(html), m.end() + 300)
            window = html[start:end]
            if "X-CSRFToken" not in window:
                findings.append(snippet)

    return findings


# -----------------------------
# Code Scanning
# -----------------------------
def find_csrf_exempt_decorators(root_dir: str) -> List[str]:
    """List occurrences of `@csrf_exempt` in source files under root_dir."""
    hits = []
    for root, _, files in os.walk(root_dir):
        for name in files:
            if not name.endswith((".py", ".html")):
                continue
            fp = os.path.join(root, name)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                continue
            if "@csrf_exempt" in text:
                hits.append(fp)
    return hits


# -----------------------------
# Optional Online Probe
# -----------------------------
def online_probe(base_url: str) -> Dict[str, object]:
    """
    Perform simple runtime checks against the given base URL.

    Checks:
    - GET `/users/login/`: verify HTML contains `name="csrfmiddlewaretoken"`.
    - Record whether a `csrftoken` cookie was set.
    """
    # Sanitize any accidental quoting/backticks in base_url provided via CLI
    base_url = (base_url or '').strip().strip("`'\"")

    result: Dict[str, object] = {
        "base_url": base_url,
        "login_has_csrf_input": None,
        "csrftoken_cookie_present": None,
        "login_html_saved": None,
        "login_status_code": None,
        "health_status_code": None,
        "health_json": None,
        "errors": [],
    }

    # Try to use `requests`; fallback to `urllib` if unavailable.
    session = None
    try:
        import requests  # type: ignore
        session = requests.Session()
        login_url = base_url.rstrip("/") + "/users/login/"
        resp = session.get(login_url, timeout=10)
        result["login_status_code"] = resp.status_code
        html = resp.text
        # Robust detection for CSRF hidden input field
        has_input = ("csrfmiddlewaretoken" in html) or (
            re.search(r'name\s*=\s*["\']csrfmiddlewaretoken["\']', html, re.IGNORECASE) is not None
        )
        result["login_has_csrf_input"] = has_input
        # Detect csrftoken cookie either from the cookie jar or Set-Cookie header.
        cookie_names = set(session.cookies.keys())
        has_cookie = ("csrftoken" in cookie_names) or ("csrftoken=" in ",".join(resp.headers.get("Set-Cookie", "") for _ in [0]))
        result["csrftoken_cookie_present"] = has_cookie
        # HTML snapshot saving is delegated to caller, which knows docs_dir.

        # Health endpoint probe
        try:
            health_url = base_url.rstrip("/") + "/health/"
            hresp = session.get(health_url, timeout=10)
            result["health_status_code"] = hresp.status_code
            if hresp.headers.get("Content-Type", "").lower().startswith("application/json"):
                try:
                    result["health_json"] = hresp.json()
                except Exception:
                    result["health_json"] = hresp.text[:1000]
            else:
                result["health_json"] = hresp.text[:1000]
        except Exception as h_exc:
            result["errors"].append(f"health probe failed: {h_exc}")
    except Exception as exc:
        result["errors"].append(f"requests probe failed: {exc}")
        try:
            from urllib.request import urlopen
            url = base_url.rstrip("/") + "/users/login/"
            with urlopen(url, timeout=10) as resp:  # nosec - diagnostic only
                html = resp.read().decode("utf-8", errors="ignore")
            has_input = ("csrfmiddlewaretoken" in html) or (
                re.search(r'name\s*=\s*["\']csrfmiddlewaretoken["\']', html, re.IGNORECASE) is not None
            )
            result["login_has_csrf_input"] = has_input
            # Cookie detection is limited with urllib; mark as unknown.
            result["csrftoken_cookie_present"] = None
            result["login_status_code"] = None
            # Snapshot saving delegated to caller

            # Health endpoint probe (basic urllib)
            try:
                from urllib.request import urlopen as _urlopen
                health_url = base_url.rstrip("/") + "/health/"
                with _urlopen(health_url, timeout=10) as hresp:  # nosec
                    result["health_status_code"] = getattr(hresp, 'status', None)
                    hbody = hresp.read().decode("utf-8", errors="ignore")
                    result["health_json"] = hbody[:1000]
            except Exception as h_exc:
                result["errors"].append(f"health probe failed: {h_exc}")
        except Exception as exc2:
            result["errors"].append(f"urllib probe failed: {exc2}")

    return result


# -----------------------------
# Main
# -----------------------------
def main(argv: Optional[List[str]] = None) -> int:
    # Basic CLI parsing for `--settings` and `--base-url`.
    argv = argv or sys.argv[1:]
    override_settings = None
    base_url = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        # Support both '--flag value' and '--flag=value' forms
        if arg.startswith("--settings="):
            override_settings = arg.split("=", 1)[1]
            i += 1
            continue
        if arg == "--settings" and i + 1 < len(argv):
            override_settings = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--base-url="):
            base_url = arg.split("=", 1)[1]
            i += 1
            continue
        if arg == "--base-url" and i + 1 < len(argv):
            base_url = argv[i + 1]
            i += 2
            continue
        i += 1

    project_root, settings_module, templates_root, app_roots, report_path, docs_dir = project_paths()
    if override_settings:
        settings_module = override_settings

    print(f"[INFO] Project root: {project_root}")
    print(f"[INFO] Using settings: {settings_module}")
    ok, err = init_django(project_root, settings_module)
    if not ok:
        print(f"[ERROR] {err}")
        return 1

    # Ensure docs directory exists and is writable; fallback to /tmp if needed.
    chosen_docs_dir = docs_dir
    try:
        os.makedirs(chosen_docs_dir, exist_ok=True)
        # Write test file to confirm permissions
        _test = os.path.join(chosen_docs_dir, ".write_test")
        with open(_test, "w", encoding="utf-8") as tf:
            tf.write("ok")
        os.remove(_test)
    except Exception:
        chosen_docs_dir = "/tmp"
        try:
            os.makedirs(chosen_docs_dir, exist_ok=True)
        except Exception:
            pass
    print(f"[INFO] Using docs dir: {chosen_docs_dir}")

    # Rebind report_path to the confirmed docs dir
    report_path = os.path.join(chosen_docs_dir, os.path.basename(report_path))

    settings_diag = collect_settings_diagnostics()

    # Template scan: project-level `templates/` and app templates.
    forms_missing: Dict[str, List[str]] = {}
    js_missing: Dict[str, List[str]] = {}

    def scan_templates_dir(dir_path: str):
        if os.path.isdir(dir_path):
            for root, _, files in os.walk(dir_path):
                for name in files:
                    if not name.endswith(".html"):
                        continue
                    fp = os.path.join(root, name)
                    missing_forms = find_forms_missing_csrf(fp)
                    missing_js = find_js_calls_missing_csrf(fp)
                    if missing_forms:
                        forms_missing[fp] = missing_forms
                    if missing_js:
                        js_missing[fp] = missing_js

    # Scan root templates.
    scan_templates_dir(templates_root)
    # Scan app `templates/` subdirs where present.
    for app_root in app_roots:
        scan_templates_dir(os.path.join(app_root, "templates"))

    # Code scan for @csrf_exempt across app roots.
    csrf_exempt_hits: List[str] = []
    for app_root in app_roots:
        csrf_exempt_hits.extend(find_csrf_exempt_decorators(app_root))

    # Optional online probe
    probe_result = None
    if base_url:
        probe_result = online_probe(base_url)

    # Render report
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as rpt:
        rpt.write("CSRF Diagnostics Report\n")
        rpt.write(f"Generated: {datetime.utcnow().isoformat()}Z\n\n")

        rpt.write("[Settings]\n")
        for k, v in settings_diag.items():
            if k == "MIDDLEWARE":
                rpt.write(f"{k}:\n")
                for mw in v:
                    rpt.write(f"  - {mw}\n")
            else:
                rpt.write(f"{k}: {v}\n")
        rpt.write("\n")

        def warn(cond: bool, msg: str):
            if cond:
                rpt.write(f"WARNING: {msg}\n")

        # Highlight common pitfalls for this deployment.
        # Note: adjust hosts/origins as you roll to production.
        cto = settings_diag.get("CSRF_TRUSTED_ORIGINS", []) or []
        # Detect malformed origins with stray quotes/backticks/spaces
        malformed = [str(o) for o in cto if ("`" in str(o) or "'" in str(o) or '"' in str(o) or str(o).strip() != str(o))]
        warn(not settings_diag.get("HAS_CSRF_MIDDLEWARE", False),
             "CsrfViewMiddleware missing from MIDDLEWARE.")
        warn(settings_diag.get("SESSION_COOKIE_SECURE", False) is not True,
             "SESSION_COOKIE_SECURE should be True on HTTPS.")
        warn(settings_diag.get("CSRF_COOKIE_SECURE", False) is not True,
             "CSRF_COOKIE_SECURE should be True on HTTPS.")
        warn((settings_diag.get("CSRF_COOKIE_SAMESITE", "") or "") not in ("Lax", "Strict"),
             "CSRF_COOKIE_SAMESITE should be 'Lax' or 'Strict'.")
        warn(settings_diag.get("SECURE_PROXY_SSL_HEADER", None) != ("HTTP_X_FORWARDED_PROTO", "https"),
             "SECURE_PROXY_SSL_HEADER should be ('HTTP_X_FORWARDED_PROTO', 'https').")
        warn(settings_diag.get("USE_X_FORWARDED_HOST", False) is not True,
             "USE_X_FORWARDED_HOST should be True behind a proxy.")
        warn(settings_diag.get("SECURE_SSL_REDIRECT", False) is not True,
             "SECURE_SSL_REDIRECT should be True to enforce HTTPS.")
        # Example production host checks (informational; not required in dev):
        warn(not any(str(h).endswith("votebem.online") for h in settings_diag.get("ALLOWED_HOSTS", [])),
             "ALLOWED_HOSTS may be missing your production domains.")
        warn(not any(str(o).startswith("https://") for o in cto),
             "CSRF_TRUSTED_ORIGINS should include full 'https://' origins.")
        warn(bool(malformed),
             f"CSRF_TRUSTED_ORIGINS contains malformed entries (quotes/backticks/spaces): {malformed}")
        rpt.write("\n")

        rpt.write("[Templates Missing CSRF Tokens]\n")
        if not forms_missing:
            rpt.write("None found.\n")
        else:
            for fp, snippets in forms_missing.items():
                rpt.write(f"- {fp}: {len(snippets)} form(s) missing csrf_token\n")
        rpt.write("\n")

        rpt.write("[JS Calls Missing X-CSRFToken]\n")
        if not js_missing:
            rpt.write("None found.\n")
        else:
            for fp, snippets in js_missing.items():
                rpt.write(f"- {fp}: {len(snippets)} suspected call(s) missing X-CSRFToken\n")
        rpt.write("\n")

        rpt.write("[@csrf_exempt Usage]\n")
        if not csrf_exempt_hits:
            rpt.write("None found.\n")
        else:
            for fp in csrf_exempt_hits:
                rpt.write(f"- {fp}\n")
        rpt.write("\n")

        if probe_result:
            rpt.write("[Online Probe]\n")
            for k, v in probe_result.items():
                rpt.write(f"{k}: {v}\n")
            rpt.write("\n")

        rpt.write("[Next Steps]\n")
        rpt.write("- Fix any warnings above in Django settings (proxy/HTTPS/CSRF).\n")
        rpt.write("- Ensure reverse proxy forwards 'X-Forwarded-Proto: https' and keeps the Host header.\n")
        rpt.write("- Access the site via https:// only in production; secure cookies are not sent on http://.\n")
        rpt.write("- Add '{% csrf_token %}' inside all '<form method=\"post\">' templates.\n")
        rpt.write("- For AJAX writes, include the 'X-CSRFToken' header using the 'csrftoken' cookie.\n")

    # Console summary
    print(f"[SUCCESS] CSRF diagnostics written to: {report_path}")
    print("[SUMMARY] Key findings:")
    print(f"  - Settings: {settings_diag.get('DJANGO_SETTINGS_MODULE')} (DEBUG={settings_diag.get('DEBUG')})")
    print(f"  - ALLOWED_HOSTS: {settings_diag.get('ALLOWED_HOSTS')} ")
    print(f"  - CSRF_TRUSTED_ORIGINS: {settings_diag.get('CSRF_TRUSTED_ORIGINS')} ")
    print(f"  - SECURE_PROXY_SSL_HEADER: {settings_diag.get('SECURE_PROXY_SSL_HEADER')} ")
    print(f"  - USE_X_FORWARDED_HOST: {settings_diag.get('USE_X_FORWARDED_HOST')} ")
    if probe_result:
        print(f"  - Online probe base: {probe_result.get('base_url')} ")
        print(f"  - Login page has CSRF input: {probe_result.get('login_has_csrf_input')} ")
        print(f"  - csrftoken cookie present: {probe_result.get('csrftoken_cookie_present')} ")
        # Save login HTML snapshot to chosen docs dir if present
        try:
            import requests  # type: ignore
            login_url = base_url.rstrip("/") + "/users/login/"
            resp = requests.get(login_url, timeout=10)
            snapshot_path = os.path.join(chosen_docs_dir, "diagnostics_login.html")
            with open(snapshot_path, "w", encoding="utf-8") as f:
                f.write(resp.text)
            print(f"  - Login HTML snapshot: {snapshot_path}")
        except Exception as snap_exc:
            print(f"  - Login HTML snapshot save failed: {snap_exc}")
    print("[NEXT] Review the report and apply fixes if any warnings are listed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] Unexpected failure: {exc}")
        raise SystemExit(1)

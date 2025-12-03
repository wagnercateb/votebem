#!/bin/bash

#==============================================================================
# Diagnose Django Dashboard Access Script
#==============================================================================
# PURPOSE:
#   Investigate why requests to '/gerencial/dashboard/' are redirecting to
#   Django's admin login, even for users flagged as staff/superuser.

# How to Run
# - On the VPS:
#   - cd /dados/votebem
#   - Copy or sync the script there if needed, then run:
#   - bash diagnose_dashboard_access.sh --project-dir /dados/votebem --service web
#   - To add a live login test, include your admin username:
#     - bash diagnose_dashboard_access.sh --project-dir /dados/votebem --service web --username vava

# WHAT THIS SCRIPT DOES:
#   - Detects Docker Compose (v2 or v1) and selects the command.
#   - Validates project directory (default: /dados/votebem).
#   - Detects service names and targets the Django web service (default: 'web').
#   - Runs an inline Python diagnostic inside the container to:
#       * Print critical Django settings (LOGIN_URL, ALLOWED_HOSTS, etc.).
#       * Resolve the URL '/gerencial/dashboard/' to its actual view function.
#       * Attempt to infer common decorators (login_required/staff_member_required)
#         by inspecting the wrapper chain.
#       * Optionally perform a real login using provided credentials and test
#         the response code and redirect chain for the dashboard URL.
#   - Performs lightweight greps across the app for 'staff_member_required' and
#     'dashboard' for additional hints.
#
# USAGE:
#   ./diagnose_dashboard_access.sh [--project-dir /dados/votebem] [--service web] [--username USER]
#   # The script will prompt for a password if --username is provided.
#
# NOTES:
#   - Avoids command chaining (&&); runs steps sequentially for clarity.
#   - If you specify --username, the script will prompt securely for a password
#     and pass it to the inline Python via environment variable. This is a best
#     effort to reduce exposure; still treat credentials carefully.
#   - Extensive output is provided to help triage configuration vs. code causes.
#
# AUTHOR: Ops Toolkit
# VERSION: 1.0
# LAST MODIFIED: 2025-11-30
#==============================================================================

set -e

echo "=== Diagnose Django Dashboard Access ==="

#------------------------------------------------------------------------------
# Defaults and argument parsing
#------------------------------------------------------------------------------
PROJECT_DIR="/dados/votebem"
SERVICE_NAME="web"
USERNAME=""

while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="$2"
      shift
      shift
      ;;
    --service)
      SERVICE_NAME="$2"
      shift
      shift
      ;;
    --username)
      USERNAME="$2"
      shift
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

echo "Target project directory: $PROJECT_DIR"
echo "Target service name: $SERVICE_NAME"
if [ -n "$USERNAME" ]; then
  echo "Target username for optional login test: $USERNAME"
fi

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Error: Project directory '$PROJECT_DIR' not found."
  exit 1
fi

cd "$PROJECT_DIR"

#------------------------------------------------------------------------------
# Determine docker compose command (v2 vs v1)
#------------------------------------------------------------------------------
COMPOSE_CMD=""
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
  else
    echo "Error: Neither 'docker compose' (v2) nor 'docker-compose' (v1) is available."
    exit 1
  fi
fi
echo "Using Compose command: $COMPOSE_CMD"

#------------------------------------------------------------------------------
# Verify the service exists
#------------------------------------------------------------------------------
SERVICES_LIST=$($COMPOSE_CMD config --services)
echo "Services detected:" 
echo "$SERVICES_LIST"

SERVICE_EXISTS=$(echo "$SERVICES_LIST" | grep -E "^${SERVICE_NAME}$" || true)
if [ -z "$SERVICE_EXISTS" ]; then
  echo "Warning: Service '$SERVICE_NAME' not found in compose config."
  echo "Proceeding anyway; if exec fails, specify a valid service via --service."
fi

#------------------------------------------------------------------------------
# Prompt for password if username given (optional login test)
#------------------------------------------------------------------------------
PASSWORD=""
if [ -n "$USERNAME" ]; then
  read -s -p "Password for '$USERNAME': " PASSWORD
  echo
fi

#------------------------------------------------------------------------------
# Light grep for hints (view decorators or routes)
#------------------------------------------------------------------------------
echo "--- Grep hints (inside container FS) ---"
$COMPOSE_CMD exec "$SERVICE_NAME" bash -lc "echo 'Searching for staff_member_required...'; grep -R 'staff_member_required' -n . | head -n 50 || true"
$COMPOSE_CMD exec "$SERVICE_NAME" bash -lc "echo 'Searching for /gerencial/dashboard route mentions...'; grep -R '/gerencial/dashboard' -n . | head -n 50 || true"

#------------------------------------------------------------------------------
# Inline Python diagnostic in container
#------------------------------------------------------------------------------
echo "--- Django inline diagnostic ---"
PY_INLINE_SCRIPT=$(cat <<'PY'
import os, sys, importlib, inspect, re

def ensure_django_setup():
    """
    Robustly initialize Django:
    - Honor existing DJANGO_SETTINGS_MODULE if it imports.
    - If it fails, try extracting from manage.py.
    - If still failing, scan for packages with settings modules.
    - Insert CWD into sys.path to ensure local packages are importable.
    """

    def try_set(ds):
        if not ds:
            return False
        try:
            importlib.import_module(ds)
            os.environ["DJANGO_SETTINGS_MODULE"] = ds
            return True
        except Exception as e:
            print(f"  Tried {ds}, import failed: {e}")
            return False

    # Ensure current directory is in import path
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # 1) Try existing DS
    if try_set(os.environ.get("DJANGO_SETTINGS_MODULE")):
        pass
    else:
        # 2) Try to read from manage.py
        detected = None
        for root, dirs, files in os.walk("."):
            if "manage.py" in files:
                mp = os.path.join(root, "manage.py")
                try:
                    with open(mp, "r", encoding="utf-8") as f:
                        txt = f.read()
                    m = re.search(r"os\.environ\.setdefault\(\s*['\"]DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", txt)
                    if m:
                        detected = m.group(1)
                        break
                except Exception:
                    pass
        if not try_set(detected):
            # 3) Candidates list (common names)
            common = [
                "votebem.settings.production",
                "votebem.settings",
                "django_votebem.settings.production",
                "django_votebem.settings",
                "config.settings",
                "core.settings",
            ]
            for mod in common:
                if try_set(mod):
                    break
            if not os.environ.get("DJANGO_SETTINGS_MODULE"):
                # 4) Scan for local packages with settings
                for entry in os.listdir("."):
                    p = os.path.join(".", entry)
                    if not os.path.isdir(p):
                        continue
                    if not os.path.exists(os.path.join(p, "__init__.py")):
                        continue
                    # settings.py
                    if os.path.exists(os.path.join(p, "settings.py")):
                        if try_set(f"{entry}.settings"):
                            break
                    # settings package
                    sp = os.path.join(p, "settings")
                    if os.path.isdir(sp) and os.path.exists(os.path.join(sp, "__init__.py")):
                        for name in ("production", "prod", "base", "dev", "local"):
                            if os.path.exists(os.path.join(sp, f"{name}.py")):
                                if try_set(f"{entry}.settings.{name}"):
                                    break
                        if os.environ.get("DJANGO_SETTINGS_MODULE"):
                            break
                if not os.environ.get("DJANGO_SETTINGS_MODULE"):
                    print("  Could not auto-detect DJANGO_SETTINGS_MODULE. Set env and retry.")

    # Finally, run django.setup()
    try:
        import django
        django.setup()
    except Exception as e:
        print("  django.setup() error:", e)

ensure_django_setup()

from django.conf import settings
from django.urls import resolve

print("Settings snapshot:")
print("  DJANGO_SETTINGS_MODULE:", os.environ.get("DJANGO_SETTINGS_MODULE"))
print("  DEBUG:", getattr(settings, "DEBUG", None))
print("  LOGIN_URL:", getattr(settings, "LOGIN_URL", None))
print("  LOGIN_REDIRECT_URL:", getattr(settings, "LOGIN_REDIRECT_URL", None))
print("  LOGOUT_REDIRECT_URL:", getattr(settings, "LOGOUT_REDIRECT_URL", None))
print("  ALLOWED_HOSTS:", getattr(settings, "ALLOWED_HOSTS", None))
print("  CSRF_TRUSTED_ORIGINS:", getattr(settings, "CSRF_TRUSTED_ORIGINS", None))
print("  SESSION_COOKIE_SECURE:", getattr(settings, "SESSION_COOKIE_SECURE", None))
print("  CSRF_COOKIE_SECURE:", getattr(settings, "CSRF_COOKIE_SECURE", None))
print("  AUTHENTICATION_BACKENDS:", getattr(settings, "AUTHENTICATION_BACKENDS", None))

path = "/gerencial/dashboard/"
print("\nResolving path:", path)
try:
    r = resolve(path)
    print("  View name:", getattr(r, "view_name", None))
    func = r.func
    mod = inspect.getmodule(func)
    print("  Function module:", getattr(mod, "__name__", None))

    chain = []
    f = func
    while True:
        modname = getattr(inspect.getmodule(f), "__name__", "unknown")
        qual = getattr(f, "__qualname__", getattr(f, "__name__", repr(f)))
        chain.append((modname, qual))
        if hasattr(f, "__wrapped__"):
            f = f.__wrapped__
        else:
            break
    print("  Wrapper chain:", chain)
    def chain_has(mod_substr):
        return any(mod_substr in m for m, _ in chain)
    print("  Has login_required:", chain_has("django.contrib.auth.decorators"))
    print("  Has staff_member_required:", chain_has("django.contrib.admin.views.decorators"))
except Exception as e:
    print("  Resolve error:", e)

user = os.environ.get("DJ_TEST_USER")
pwd = os.environ.get("DJ_TEST_PASSWORD")
if user and pwd:
    print("\nPerforming login test for user:", user)
    from django.test import Client
    from django.test.utils import override_settings
    # Ensure 'testserver' appears in ALLOWED_HOSTS for Client, and also send HTTP_HOST matching production.
    current_hosts = list(getattr(settings, "ALLOWED_HOSTS", [])) or []
    if "testserver" not in current_hosts:
        current_hosts.append("testserver")
    target_host = "votebem.online"
    if target_host not in current_hosts:
        current_hosts.append(target_host)
    with override_settings(ALLOWED_HOSTS=current_hosts):
        c = Client()
        ok = c.login(username=user, password=pwd)
        print("  login_ok:", ok)
        resp = c.get(path, follow=False, HTTP_HOST=target_host)
        print("  response_status:", resp.status_code)
        if 300 <= resp.status_code < 400:
            print("  redirect_to:", resp.headers.get("Location"))
        else:
            print("  non-redirect response, content length:", len(resp.content))
PY
)

# Encode the Python script safely to avoid quoting issues across shells
PY_B64=$(printf "%s" "$PY_INLINE_SCRIPT" | base64 | tr -d '\n')

# Build exec command; pass credentials if provided
if [ -n "$USERNAME" ]; then
  $COMPOSE_CMD exec -e DJ_TEST_USER="$USERNAME" -e DJ_TEST_PASSWORD="$PASSWORD" "$SERVICE_NAME" bash -lc "printf '%s' '$PY_B64' | base64 -d > /tmp/dj_diag.py ; python /tmp/dj_diag.py"
else
  $COMPOSE_CMD exec "$SERVICE_NAME" bash -lc "printf '%s' '$PY_B64' | base64 -d > /tmp/dj_diag.py ; python /tmp/dj_diag.py"
fi

echo "--- Diagnostic complete ---"
echo "If needed, re-run with --username USER to include a live login test."
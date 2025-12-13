#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import importlib


def main():
    """Run administrative tasks."""
    # Default to the production settings module if nothing is provided via
    # environment. This maintains the intended runtime behavior.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.production')

    # Defensive fallback:
    # In some environments (e.g., Docker with an outdated .env), the
    # DJANGO_SETTINGS_MODULE may be set to a non-existent module such as
    # 'votebem.settings.development'. That causes management commands like
    # `python manage.py shell` to crash BEFORE Django loads.
    #
    # To avoid that failure mode, try importing the configured settings
    # module and, if the module is missing, force a fallback to
    # 'votebem.settings.production'. This preserves expected production behavior
    # while ensuring that CLI/admin commands remain usable even if the
    # environment contains legacy values.
    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
    if settings_module:
        try:
            importlib.import_module(settings_module)
        except ModuleNotFoundError:
            # Only fallback when the module itself is not found. We do NOT
            # swallow other ImportError cases that indicate real problems
            # inside the settings code.
            os.environ['DJANGO_SETTINGS_MODULE'] = 'votebem.settings.production'

    # Optional: enable debugpy remote attach when environment variables are set.
    # This allows running the server in TRAE and attaching breakpoints from VSCode.
    # Usage:
    #   set DEBUGPY_LISTEN=127.0.0.1:5678
    #   set DEBUGPY_WAIT=0  (set to 1 to wait for the debugger to attach before continuing)
    #   python manage.py runserver 127.0.0.1:8000 --noreload
    try:
        listen_cfg = os.environ.get("DEBUGPY_LISTEN")
        if listen_cfg:
            import debugpy  # type: ignore
            host, port_str = listen_cfg.split(":")
            debugpy.listen((host, int(port_str)))
            # Optionally block until client attaches
            if os.environ.get("DEBUGPY_WAIT", "0") == "1":
                debugpy.wait_for_client()
    except Exception:
        # Fail-safe: never break server startup due to debugging setup
        pass
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

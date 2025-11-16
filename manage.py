#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'votebem.settings.development')

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

"""
Development logging utility.

Provides a simple function `dev_log(message)` that:
- Prints the message to stdout for immediate visibility during dev runs.
- Appends the same message to a log file defined by the environment variable
  `VOTEBEM_DEBUG_LOG`. If not set, falls back to `logs\django_dev_debug.log`.

Usage:
    from votebem.utils.devlog import dev_log
    dev_log("DEBUG: Something happened")

This is intended for development-only verbose logging and complements
the standard Django logging configuration.
"""

import os
from datetime import datetime


def _get_log_file_path() -> str:
    """Resolve the development log file path from environment or default."""
    # Prefer explicit environment variable set by startup_dev.bat
    path = os.environ.get("VOTEBEM_DEBUG_LOG")
    if not path:
        # Default to logs directory under current working directory
        path = os.path.join(os.getcwd(), "logs", "django_dev_debug.log")
    return path


def dev_log(*args, sep: str = " ", end: str = "\n") -> None:
    """
    Print-compatible development logger.

    - Accepts any number of arguments like built-in `print` and joins them
      using `sep`. `end` is honored for console output but file logging
      always appends a newline for readability.
    - Prefixes each line with a timestamp for easier correlation.
    - Creates the parent directory if it doesn't exist.
    - Silently ignores file I/O errors to avoid disrupting development flow.
    """
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = sep.join(str(a) for a in args)
        line = f"[{ts}] {msg}"
        # Print to console (preserve end behavior)
        print(line, end=end)

        # Append to file
        log_path = _get_log_file_path()
        parent = os.path.dirname(log_path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # Do not raise in dev logging; keep development flow smooth.
        pass
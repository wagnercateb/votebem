# Debugging Django with debugpy (Windows)

This project’s `scripts\windows\startup_dev.bat` can start Django under `debugpy` so you can attach a debugger and use breakpoints.

## Quick Start (VS Code)

- Open the workspace folder: `c:\Users\User\Dados\Tecnicos\HardESoftware\EmDesenvolvimento\VotoBomPython\django_votebem`.
- Ensure the Python extension is installed and the interpreter is set to the project’s `.venv`.
- Use the preconfigured attach profile:
  - Open the Run and Debug view.
  - Select `Attach to Django (debugpy)` from the dropdown.
  - Click the green Start button.
- Start the dev server script:
  - Run `scripts\windows\startup_dev.bat`.
  - The script waits for the debugger by default and prints attach instructions.
  - Once VS Code attaches, Django will start and breakpoints will work.

## Dev Log File

- The dev script sets the environment variable `VOTEBEM_DEBUG_LOG` to a default path:
  - `logs\django_dev_debug.log` under the project root.
- Verbose debug messages from services (e.g., Câmara API calls) are printed and also appended to this file.
- To change the path, set `VOTEBEM_DEBUG_LOG` before running the script.

## Controlling wait behavior

The script supports a `DEBUGPY_WAIT` flag:

- CMD: `set DEBUGPY_WAIT=0` ; run `scripts\windows\startup_dev.bat`
- PowerShell: `$env:DEBUGPY_WAIT=0` ; run `scripts\windows\startup_dev.bat`

Values:
- `1` (default): Wait for the debugger to attach before starting Django.
- `0`: Start Django immediately and allow attaching later.

## Autoreload

- `DJANGO_AUTORELOAD=0` (default) runs without Django’s reloader for stable breakpoints.
- To enable reloads: set `DJANGO_AUTORELOAD=1` before running the script.

## Notes on IDEs

- VS Code works out of the box with `debugpy`.
- PyCharm’s native debugger does not attach to `debugpy`; use VS Code or run Django directly in PyCharm’s own debug configuration without `debugpy`.

## Troubleshooting

- If attach fails, verify the port and host: `127.0.0.1:5678`.
- Ensure your IDE uses the project’s `.venv` interpreter.
- Firewalls can block `127.0.0.1:5678`; allow the connection when prompted.
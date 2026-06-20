"""Thin personal launcher for the WhisperJAV GUI (development build).

Built into WhisperJAV.exe with PyInstaller. It does NOT bundle WhisperJAV or its
dependencies — it simply starts the GUI using the project's local virtual
environment (.venv), so the exe stays small and always runs your current
(patched) source via the editable install.

Resolution order for the venv:
  1. a `.venv` next to the exe (keeps it portable if the exe lives in the repo)
  2. the absolute repo path this exe was built from (fallback if the exe is moved)
"""

import os
import subprocess
import sys
from pathlib import Path

# Absolute fallback — the repo this launcher was built from.
_BUILD_TIME_REPO = r"c:\Users\steve1316\Documents\GitHub\WhisperJAV-main"

# Windows process-creation flags (avoid importing values that may be absent).
_DETACHED_PROCESS = 0x00000008
_CREATE_NO_WINDOW = 0x08000000


def _error_box(message: str) -> None:
    """Show a native message box (we run --windowed, so there's no console)."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "WhisperJAV Launcher", 0x10)
    except Exception:
        # Last resort: write a file next to the exe so the failure isn't silent.
        try:
            with open(Path(_base_dir()) / "whisperjav_launcher_error.txt", "w", encoding="utf-8") as fh:
                fh.write(message)
        except Exception:
            pass


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _find_repo_root() -> Path | None:
    candidates = [_base_dir(), Path(_BUILD_TIME_REPO)]
    for root in candidates:
        if (root / ".venv" / "Scripts" / "pythonw.exe").exists():
            return root
    return None


def main() -> int:
    root = _find_repo_root()
    if root is None:
        _error_box(
            "Could not find the WhisperJAV virtual environment (.venv).\n\n"
            "Place WhisperJAV.exe inside the project folder (next to the .venv "
            "directory), or rebuild the launcher from the project you set up.\n\n"
            f"Looked next to the exe and at:\n{_BUILD_TIME_REPO}"
        )
        return 1

    pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
    try:
        subprocess.Popen(
            [str(pythonw), "-m", "whisperjav.webview_gui.main"],
            cwd=str(root),
            creationflags=_DETACHED_PROCESS | _CREATE_NO_WINDOW,
        )
    except Exception as exc:  # noqa: BLE001
        _error_box(f"Failed to start WhisperJAV GUI:\n\n{type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

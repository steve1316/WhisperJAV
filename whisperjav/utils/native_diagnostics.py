#!/usr/bin/env python3
"""Native crash diagnostics for C-level faults that Python never sees.

A GPU/ctranslate2 fault kills the process at the OS level before any Python
exception handler runs, so the only trace left is a bare Windows exit code such
as 0xC0000094 (integer divide by zero). Enabling `faulthandler` makes the
interpreter dump the Python stack of every thread at fault time, naming the line
that called into the failing native code.
"""

import faulthandler
import os
import sys


def install_native_diagnostics():
    """Enable native fault capture and optional blocking-mode GPU debugging.

    Always turns on `faulthandler` so a fatal native signal (SIGSEGV, SIGFPE,
    SIGABRT) dumps every thread's Python traceback to stderr before the process
    dies. When `WHISPERJAV_DEBUG_NATIVE` is set to a truthy value, it also forces
    synchronous CUDA launches and verbose CTranslate2 logging so the faulting GPU
    op is reported at its real call site. Blocking mode slows transcription, so it
    stays opt-in. Must run before torch or ctranslate2 import for the env vars to
    take effect.
    """
    # faulthandler is cheap and safe to leave on permanently. Register it for all
    # threads so a fault inside a worker thread still prints a usable traceback.
    if not faulthandler.is_enabled():
        faulthandler.enable(file=sys.stderr, all_threads=True)

    if _is_truthy(os.environ.get("WHISPERJAV_DEBUG_NATIVE")):
        # setdefault so an explicit value the user already exported wins.
        os.environ.setdefault("CUDA_LAUNCH_BLOCKING", "1")
        os.environ.setdefault("CT2_VERBOSE", "3")


def _is_truthy(value):
    """Return whether a string looks like an explicit enable flag.

    Args:
        value: The raw environment variable value, or None when unset.

    Returns:
        True when `value` is one of "1", "true", "yes", or "on" (case-insensitive).
    """
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

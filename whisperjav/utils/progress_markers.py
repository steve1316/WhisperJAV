"""Stdout progress markers for multi-file transcription/ensemble runs.

Producers (main.py, ensemble orchestrator/worker) print one marker line per file;
the webview GUI consumer (api.py) parses it to drive the live progress indicator.
Kept in a single module so the producer string and the parser cannot drift.
"""
import re
from typing import Any, Dict, Optional

# Matches both:
#   "Transcribing [4/20]: name.mp4"
#   "Transcribing [pass 1/2] [4/20]: name.mp4"
_TRANSCRIBE_RE = re.compile(
    r"Transcribing(?:\s+\[pass\s+(\d+)/(\d+)\])?\s+\[(\d+)/(\d+)\]:\s+(.+)"
)


def transcribe_marker(name: str, current: int, total: int,
                      pass_number: Optional[int] = None,
                      pass_total: Optional[int] = None) -> str:
    """Build the stdout marker line for a file about to be transcribed.

    A pass label is included only when ``pass_total`` is provided and > 1, so
    single-pass runs read as plain transcription.
    """
    if pass_total is not None and pass_total > 1:
        return (f"Transcribing [pass {pass_number}/{pass_total}] "
                f"[{current}/{total}]: {name}")
    return f"Transcribing [{current}/{total}]: {name}"


def parse_transcribe_marker(line: str) -> Optional[Dict[str, Any]]:
    """Parse a marker line; return None when the line is not a marker."""
    m = _TRANSCRIBE_RE.match(line.lstrip())
    if not m:
        return None
    return {
        "pass_number": int(m.group(1)) if m.group(1) else None,
        "pass_total": int(m.group(2)) if m.group(2) else None,
        "current": int(m.group(3)),
        "total": int(m.group(4)),
        "name": m.group(5).strip(),
    }


# Overall-progress marker: a single 0-100 percent that blends the current file
# index with the within-file scene fraction, so the GUI bar moves smoothly even
# while one long file is being transcribed.
#   "Transcribing-progress [67]"
_PROGRESS_RE = re.compile(r"Transcribing-progress \[(\d+)\]")


def progress_marker(percent: int) -> str:
    """Build the overall-progress marker line for the given 0-100 percent."""
    return f"Transcribing-progress [{percent}]"


def parse_progress_marker(line: str) -> Optional[int]:
    """Parse an overall-progress marker; return the int percent, or None."""
    m = _PROGRESS_RE.match(line.lstrip())
    return int(m.group(1)) if m else None

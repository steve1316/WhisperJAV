"""Continuation stitcher.

Re-joins subtitle cues that were split mid-sentence by upstream segmentation
(scene/VAD boundaries) or by per-cue translation. The tell-tale sign is a short
tail cue, a few milliseconds after its head, that begins with an ellipsis — e.g.

    224  00:18:23,078 --> 00:18:24,278  He wails after he uses it, poor baby.
    225  00:18:24,306 --> 00:18:24,866  …and then he'll really let loose.

These are one continuous utterance. Splitting them leaves the tail too short to
read (high CPS) and visually fragmented. This module merges such pairs back into
a single cue spanning the full time range, preserving the original text verbatim.

The merge is intentionally high-precision: it only fires when cues are nearly
adjacent in time and the join is signalled either by a leading ellipsis on the
tail, or by a head with no sentence-final punctuation followed by a lowercase
tail. It never invents or drops words.
"""

import re
from datetime import timedelta
from pathlib import Path
from typing import List, Union

import srt

# Default thresholds.
DEFAULT_MAX_GAP = timedelta(milliseconds=450)
DEFAULT_OVERLAP_TOLERANCE = timedelta(milliseconds=250)
DEFAULT_MAX_MERGED_CHARS = 200

# Punctuation that marks the end of a sentence (Latin + CJK fullwidth forms).
_TERMINAL_PUNCT = ".!?…。！？"
# Trailing characters to look past when checking for terminal punctuation.
_CLOSERS = " \t\r\n\"'»”’）)]}】」』"
# Leading characters to look past when checking how the tail starts.
_OPENERS = " \t\r\n\"'«“‘（([{【「『…."

# Ellipsis runs at the very end / very start of a fragment — these are
# segment-boundary artifacts (the ASR/translator marking a cut), not real pauses.
_TRAILING_ELLIPSIS = re.compile(r"\s*(?:…|\.\.\.)\s*$")
_LEADING_ELLIPSIS = re.compile(r"^\s*(?:…|\.\.\.)\s*")


def _ends_sentence(text: str) -> bool:
    stripped = text.rstrip(_CLOSERS)
    return bool(stripped) and stripped[-1] in _TERMINAL_PUNCT


def _starts_with_ellipsis(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("…") or stripped.startswith("...")


def _starts_lowercase(text: str) -> bool:
    stripped = text.lstrip(_OPENERS)
    if not stripped:
        return False
    first = stripped[0]
    return first.isalpha() and first.islower()


def _is_continuation(prev_content: str, next_content: str) -> bool:
    """True if next_content is the continuation of prev_content."""
    if _starts_with_ellipsis(next_content):
        return True
    if not _ends_sentence(prev_content) and _starts_lowercase(next_content):
        return True
    return False


def _join(prev_content: str, next_content: str) -> str:
    """Join two fragments, cleaning up the seam punctuation.

    The cues were split at a pause the ASR/translator marked with ellipses (and
    sometimes a spurious sentence-ending period). Stitching them back must not
    leave doubled markers like ``"… …"`` or ``". …"``. So at the seam we drop the
    trailing/leading ellipsis artifacts and pick a single natural connector:

    - ``"while…" + "…I'm"``        -> ``"while… I'm"``   (one ellipsis kept)
    - ``"poor baby." + "…and"``    -> ``"poor baby… and"`` (false period -> ellipsis)
    - ``"Really?" + "…I guess"``   -> ``"Really? I guess"`` (real ? kept, no double)
    - ``"the one that" + "a cat"`` -> ``"the one that a cat"`` (plain space)
    """
    head = prev_content.rstrip()
    tail = next_content.lstrip()

    head_had_ellipsis = bool(_TRAILING_ELLIPSIS.search(head))
    tail_had_ellipsis = bool(_LEADING_ELLIPSIS.search(tail))
    head = _TRAILING_ELLIPSIS.sub("", head)
    tail = _LEADING_ELLIPSIS.sub("", tail)

    if not head:
        return ("… " + tail) if (head_had_ellipsis or tail_had_ellipsis) else tail
    if not tail:
        return head + ("…" if head_had_ellipsis else "")

    boundary_ellipsis = head_had_ellipsis or tail_had_ellipsis
    last = head[-1]
    if last == ".":
        # A period at a split point is almost always a false sentence end; if the
        # seam was a trailing-off pause, render it as a single ellipsis instead.
        if boundary_ellipsis:
            head = head[:-1].rstrip()
            connector = "… "
        else:
            connector = " "
    elif last in "?!" or last in ",;:":
        # Real punctuation — keep it, just add a space (never a second ellipsis).
        connector = " "
    else:
        connector = "… " if boundary_ellipsis else " "

    return head + connector + tail


def stitch_continuations(
    subs: List[srt.Subtitle],
    *,
    max_gap: timedelta = DEFAULT_MAX_GAP,
    overlap_tolerance: timedelta = DEFAULT_OVERLAP_TOLERANCE,
    max_merged_chars: int = DEFAULT_MAX_MERGED_CHARS,
    strip_leading_ellipsis: bool = True,
) -> List[srt.Subtitle]:
    """Merge mid-sentence split cues into their preceding cue.

    Args:
        subs: subtitles in chronological order.
        max_gap: largest forward gap (next.start - prev.end) still treated as a split.
        overlap_tolerance: largest backward overlap still treated as a split.
        max_merged_chars: skip the merge if the combined text would exceed this.
        strip_leading_ellipsis: drop a leading boundary ellipsis from each final
            cue (e.g. a cue that opens with "…playing" after an unmerged neighbour).

    Returns:
        A new list of subtitles with continuation cues merged. Indexes are
        renumbered from 1. Input is not mutated.
    """
    if not subs:
        return []

    merged: List[srt.Subtitle] = []
    current = srt.Subtitle(
        index=subs[0].index,
        start=subs[0].start,
        end=subs[0].end,
        content=subs[0].content,
        proprietary=subs[0].proprietary,
    )

    for nxt in subs[1:]:
        gap = nxt.start - current.end
        combined_len = len(current.content) + len(nxt.content)
        if (
            -overlap_tolerance <= gap <= max_gap
            and combined_len <= max_merged_chars
            and _is_continuation(current.content, nxt.content)
        ):
            current.content = _join(current.content, nxt.content)
            current.end = max(current.end, nxt.end)
        else:
            merged.append(current)
            current = srt.Subtitle(
                index=nxt.index,
                start=nxt.start,
                end=nxt.end,
                content=nxt.content,
                proprietary=nxt.proprietary,
            )
    merged.append(current)

    for i, sub in enumerate(merged, 1):
        sub.index = i
        if strip_leading_ellipsis:
            sub.content = _LEADING_ELLIPSIS.sub("", sub.content, count=1)
    return merged


def stitch_srt_file(path: Union[str, Path], **kwargs) -> int:
    """Stitch continuation cues in an .srt file in place.

    Returns the number of merges performed (0 if the file was left unchanged).
    Keyword arguments are forwarded to :func:`stitch_continuations`.
    """
    path = Path(path)
    subs = list(srt.parse(path.read_text(encoding="utf-8")))
    stitched = stitch_continuations(subs, **kwargs)
    merges = len(subs) - len(stitched)
    if merges > 0:
        path.write_text(srt.compose(stitched), encoding="utf-8")
    return merges


def stitch_srt_file_safe(path: Union[str, Path], on_error=None) -> int:
    """Best-effort wrapper around stitch_srt_file that never raises.

    Args:
        path: Path to the .srt file. A missing file is treated as a no-op.
        on_error: Optional callback invoked with the exception when stitching fails.

    Returns:
        Number of merges performed, or 0 if the file was missing, unchanged, or errored.
    """
    try:
        if Path(path).exists():
            return stitch_srt_file(path)
    except Exception as e:
        if on_error is not None:
            on_error(e)
    return 0

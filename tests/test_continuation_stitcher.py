#!/usr/bin/env python3
"""Tests for the continuation stitcher.

The stitcher merges subtitle cues that were split mid-sentence — the hallmark
being a tail cue that begins with an ellipsis (e.g. "…and then he'll really let
loose.") sitting a few milliseconds after the head cue. These are one continuous
utterance and should display as a single cue.
"""

from datetime import timedelta

import srt

from whisperjav.modules.continuation_stitcher import (
    stitch_continuations,
    stitch_srt_file,
)


def _sub(index, start_s, end_s, content):
    return srt.Subtitle(
        index=index,
        start=timedelta(seconds=start_s),
        end=timedelta(seconds=end_s),
        content=content,
    )


def test_merges_ellipsis_continuation_into_previous_cue():
    # The exact reported case (cues 224/225), 28 ms apart.
    subs = [
        _sub(1, 23.078, 24.278, "He wails after he uses it, poor baby."),
        _sub(2, 24.306, 24.866, "…and then he'll really let loose."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 1
    # The spurious segment-end period becomes a single trailing-off ellipsis;
    # the tail's leading continuation ellipsis is absorbed (no ". …" or "… …").
    assert out[0].content == (
        "He wails after he uses it, poor baby… and then he'll really let loose."
    )


def test_merged_cue_spans_full_time_range():
    subs = [
        _sub(1, 23.078, 24.278, "He wails after he uses it, poor baby."),
        _sub(2, 24.306, 24.866, "…and then he'll really let loose."),
    ]

    out = stitch_continuations(subs)

    assert out[0].start == timedelta(seconds=23.078)
    assert out[0].end == timedelta(seconds=24.866)


def test_collapses_double_ellipsis_at_boundary():
    # Two ellipses meeting at the seam ("while…" + "…I'm") collapse to one.
    # A mid-text ellipsis ("you know...") is left untouched.
    subs = [
        _sub(1, 1.0, 2.0, "you know... while…"),
        _sub(2, 2.05, 3.0, "…I'm scrolling through my phone…"),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 1
    assert out[0].content == "you know... while… I'm scrolling through my phone…"


def test_keeps_question_mark_and_absorbs_leading_continuation_ellipsis():
    # A real "?" is preserved; only the tail's leading continuation ellipsis goes.
    subs = [
        _sub(1, 1.0, 2.0, "Really?"),
        _sub(2, 2.05, 3.0, "…I guess so."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 1
    assert out[0].content == "Really? I guess so."


def test_strips_leading_ellipsis_from_standalone_cue():
    # A cue that opens with a continuation ellipsis but is too far away to merge
    # still gets that leading boundary ellipsis cleaned up.
    subs = [
        _sub(1, 1.0, 2.0, "A complete thought."),
        _sub(2, 30.0, 31.0, "…playing with that cable."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 2
    assert out[1].content == "playing with that cable."


def test_default_gap_merges_short_pause_continuation():
    # ~420 ms apart with a continuation ellipsis — merged under the default gap.
    subs = [
        _sub(1, 1.0, 2.0, "scrolling through my phone…"),
        _sub(2, 2.42, 3.0, "…playing with that cable."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 1
    assert out[0].content == "scrolling through my phone… playing with that cable."


def test_does_not_merge_when_gap_too_large():
    # A 3-second gap means these are not a split utterance.
    subs = [
        _sub(1, 10.0, 12.0, "First complete thought."),
        _sub(2, 15.0, 16.0, "…second thought entirely."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 2


def test_does_not_merge_two_complete_sentences():
    # No ellipsis, previous ends in terminal punctuation, next starts uppercase.
    subs = [
        _sub(1, 1.0, 2.0, "That was expensive."),
        _sub(2, 2.1, 3.0, "It really was."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 2


def test_merges_dangling_lowercase_continuation_without_ellipsis():
    # Split with no ellipsis: head has no terminal punctuation, tail starts lowercase.
    subs = [
        _sub(1, 1.0, 2.0, "I have no idea if he"),
        _sub(2, 2.05, 3.0, "even notices the stench."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 1
    assert out[0].content == "I have no idea if he even notices the stench."


def test_does_not_merge_when_result_would_be_too_long():
    long_head = "word " * 40  # ~200 chars on its own
    subs = [
        _sub(1, 1.0, 5.0, long_head.strip()),
        _sub(2, 5.05, 6.0, "…and a continuation."),
    ]

    out = stitch_continuations(subs, max_merged_chars=120)

    assert len(out) == 2


def test_chains_multiple_continuation_fragments():
    subs = [
        _sub(1, 1.0, 2.0, "The automated kind"),
        _sub(2, 2.05, 3.0, "…basically"),
        _sub(3, 3.05, 4.0, "…the expensive sort."),
    ]

    out = stitch_continuations(subs)

    assert len(out) == 1
    assert out[0].start == timedelta(seconds=1.0)
    assert out[0].end == timedelta(seconds=4.0)


def test_stitch_srt_file_merges_and_reports_count(tmp_path):
    src = tmp_path / "sample.english.srt"
    subs = [
        _sub(1, 23.078, 24.278, "He wails after he uses it, poor baby."),
        _sub(2, 24.306, 24.866, "…and then he'll really let loose."),
        _sub(3, 44.382, 46.762, "A separate, unrelated line."),
    ]
    src.write_text(srt.compose(subs), encoding="utf-8")

    merged = stitch_srt_file(src)

    assert merged == 1
    result = list(srt.parse(src.read_text(encoding="utf-8")))
    assert len(result) == 2
    assert result[0].index == 1
    assert result[1].index == 2
    assert "let loose" in result[0].content

# WhisperJAV Fork

This is a fork of the original WhisperJAV project with additional features and improvements.

## Changelog

### 2026-07-20
- Add quiet-audio controls for whisper/ASMR videos: neural speech enhancer, VAD and scene-energy thresholds, and hallucination suppression, in both the CLI and GUI.

### 2026-06-19
- Add native crash diagnostics to surface C-level GPU faults as Python tracebacks.
- Support non-Japanese source language in translation.
- Add tab-aware drag-and-drop file input to the GUI.
- Add continuation stitcher to rejoin split mid-sentence cues.
- Add per-file and scene-blended transcription progress markers.
- Add per-batch translation progress markers for terminal and GUI.
- Centralize SRT output naming with whisperjav.{lang}.srt scheme.

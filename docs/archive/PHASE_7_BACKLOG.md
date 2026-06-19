# Phase 7 Status

## Done in this pass

- Added `requirements.txt`.
- Added stronger FFmpeg/FFprobe checks.
- Installed and integrated optional `srt` parser support.
- Improved fallback SRT parsing.
- Added basic `draft_doctor.py` for draft health checks and auto-repair.
- Connected doctor checks into the Long Story GUI preflight.
- Added draft JSON checks after draft creation.
- Added portable FFmpeg/FFprobe runtime detection.
- Added prepared narration file/folder import.
- Added optional PySceneDetect source-range selection placeholder.
- Added PySide6 MVP app at `main.py` and `app/`.
- Added PyInstaller packaging script and built `dist/CapCutLongStoryStudio/CapCutLongStoryStudio.exe`.

## Skipped by request

- Voice Reading / Text-To-Speech (TTS) generation (completely removed from scope).
- Story/script text input, chunking, and previewing (completely removed from scope).
- Pydub-based background music mixing and ducking (BGM is added as a parallel track directly).

## Deferred

- OpenTimelineIO format timeline integration.
- Advanced draft repair, beyond warning/report checks.

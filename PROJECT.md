# CapCut Long Story Studio — Next-Gen Architecture & Migration Blueprint

> **Scope of this document.** This is the **R&D roadmap** for the experimental Tauri + Rust branch (`src-tauri/`, `src/`). It is *not* the shipping product.
>
> The **release runtime is Python / PySide6** at `0.1.0-mvp` — see [`docs/MVP_RESEARCH_REPORT.md`](docs/MVP_RESEARCH_REPORT.md) and [`docs/MVP_RELEASE_GUIDE.md`](docs/MVP_RELEASE_GUIDE.md). The Tauri branch is excluded from the EXE bundle until the Rust backend writes a complete CapCut timeline and passes compatibility testing.
>
> Milestone statuses below were corrected on 2026-08-07 after verification against the code; several were marked DONE prematurely.

## Architecture Overview
Target architecture for the R&D branch: a lightweight **Tauri + Rust + Web UI (HTML5/WebGL)** desktop app.

- **Frontend**: Tauri Webview UI, HTML5 Canvas / WebGL 2D Render Engine (60fps), Studio Dark Obsidian (`#121214`) Theme with Accent Cyan (`#00F2FE`) & Violet (`#7F00FF`).
- **Backend**: Rust 2021 Edition, Tokio async runtime, Serde JSON streaming serializer, Lazy Media Metadata Probe (FFprobe pipe / FFmpeg bindings), Chunked SRT parser (Nom / custom zero-copy scanner).
- **Inter-process**: Tauri IPC (`#[tauri::command]`) zero-copy byte buffers for canvas frame sync, async event streaming for progress updates.

## Milestones & Status

Status vocabulary: **SCAFFOLDED** = code exists and compiles, behaviour unverified · **PARTIAL** = works for a subset · **DONE** = verified against the acceptance criteria in the Scope column.

| # | Milestone Name | Scope | Dependencies | Status |
|---|----------------|-------|--------------|--------|
| M0 | Baseline Codebase Exploration | Analyze current Python CapCut JSON structures, keyframe calculations, SRT logic, media probe | None | DONE |
| M1 | Canvas Visual Preview (R1) | HTML5 Canvas/WebGL 60fps render loop, Keyframe (scale/rotate/pos/alpha), Transition simulation, Scrub Bar | M0 | SCAFFOLDED |
| M2 | Rust Backend Optimization (R2) | Lazy Metadata streaming, Chunked SRT parser (>5k lines), <50MB RAM, <0.1s JSON output, <15% CPU load for 1-3h media | M0 | PARTIAL |
| M3 | Studio Dark Theme UX & Migration Plan (R3) | Commercial 3-column `#121214` Dark Theme UI layout, Step-by-step Tauri+Rust migration blueprint & CapCut JSON engine integration | M1, M2 | SCAFFOLDED |
| M4 | Review, Verification & Forensic Audit | Verification by Reviewer/Challenger subagents and Forensic Integrity Audit by Auditor subagent | M1, M2, M3 | BLOCKED |

### Verification notes (2026-08-07)

What exists: 599 lines of Rust across `src-tauri/src/` (4 `#[tauri::command]` entry points: `export_capcut_draft`, `probe_media_file`, `parse_srt_file`, `run_python_hybrid_sidecar`) and 1,361 lines of TypeScript/React across `src/`.

**M2 is PARTIAL, not DONE.** `src-tauri/src/engine/draft.rs :: export_draft` writes `draft_content.json` and `draft_meta_info.json`, but emits `"audios": []`, `"texts": []`, `"transitions": []` and `"keyframes": []` as empty arrays. It does not yet produce voice, subtitle, transition or keyframe content — the core of what the Python pipeline does. The performance targets (<50MB RAM, <0.1s JSON, <15% CPU) have no benchmark evidence in the repo.

**M1 and M3 are SCAFFOLDED.** The render loop, WebGL renderer and three-column layout exist as code. Neither has verification evidence — no screenshots, no measured frame rate, no test.

**M4 is BLOCKED, and cannot be DONE.** It depends on M1–M3, none of which are complete. An audit of unverified milestones cannot itself be a completed audit. There are **zero Rust tests** in `src-tauri/` (`#[test]` / `#[cfg(test)]` count: 0).

### Exit criteria for the Tauri branch

Before this branch can be considered for release, in order:

1. `export_draft` emits a complete timeline — audio, SRT text, transitions, keyframes — matching what `capcut_draft_creator.py` produces.
2. A draft written by the Rust path opens correctly in real CapCut PC.
3. Rust test coverage for the draft, mixer, probe and SRT engines.
4. Measured benchmarks for the M2 performance targets.
5. Functional parity against the Python pipeline, tracked in `docs/VORTEX_FUNCTIONAL_PARITY.md`.

## Interface Contracts & Data Models
- **Keyframe Evaluator Schema**: Linear/Cubic Bezier interpolation for Position X/Y, Scale X/Y, Rotation, Opacity.
- **Transition Evaluator Schema**: Crossfade, Wipe, Zoom-in, Slide effects interpolated over frame sequence.
- **CapCut JSON Schema Target**: Schema version matching current CapCut desktop draft format (`draft_content.json`, `draft_meta_info.json`).

## Code Layout (Target Tauri + Rust Architecture)
```
capcut-studio-tauri/
├── src-tauri/
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs
│   │   ├── capcut/
│   │   │   ├── draft.rs          # CapCut JSON draft generator & compact writer
│   │   │   ├── keyframe.rs       # Keyframe calculation engine
│   │   │   ├── transition.rs     # Transition manager
│   │   │   └── srt.rs            # Zero-copy chunked SRT parser
│   │   ├── media/
│   │   │   ├── probe.rs          # Lazy FFprobe / MediaInfo probe stream
│   │   │   └── mixer.rs          # BGM & video background planner (<15% CPU)
│   │   └── state.rs              # App state (<50MB RAM target)
├── src/
│   ├── index.html
│   ├── styles/
│   │   └── theme.css             # Studio Obsidian Dark Theme #121214
│   ├── components/
│   │   ├── MediaLibrary.tsx       # Column 1: Ingredients & Raw Assets
│   │   ├── CanvasPreview.tsx      # Column 2: HTML5/WebGL 60fps Preview & Scrub Bar
│   │   ├── PresetTimeline.tsx     # Column 2/3: Keyframe & Transition Presets, Progress
│   │   └── Inspector.tsx          # Column 3: Properties & CapCut Export Config
│   └── engine/
│       ├── render_loop.ts         # 60fps Canvas Render Loop
│       ├── keyframe_interpolator.ts
│       └── transition_shaders.ts  # WebGL Transition shaders
```

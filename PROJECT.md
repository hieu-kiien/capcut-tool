# CapCut Long Story Studio — Next-Gen Architecture & Migration Blueprint

## Architecture Overview
Transitioning from PySide6 Python monolith to a high-performance, ultra-lightweight **Tauri + Rust + Web UI (HTML5/WebGL)** desktop application architecture for 100% commercial readiness.

- **Frontend**: Tauri Webview UI, HTML5 Canvas / WebGL 2D Render Engine (60fps), Studio Dark Obsidian (`#121214`) Theme with Accent Cyan (`#00F2FE`) & Violet (`#7F00FF`).
- **Backend**: Rust 2021 Edition, Tokio async runtime, Serde JSON streaming serializer, Lazy Media Metadata Probe (FFprobe pipe / FFmpeg bindings), Chunked SRT parser (Nom / custom zero-copy scanner).
- **Inter-process**: Tauri IPC (`#[tauri::command]`) zero-copy byte buffers for canvas frame sync, async event streaming for progress updates.

## Milestones & Status
| # | Milestone Name | Scope | Dependencies | Status |
|---|----------------|-------|--------------|--------|
| M0 | Baseline Codebase Exploration | Analyze current Python CapCut JSON structures, keyframe calculations, SRT logic, media probe | None | DONE |
| M1 | Canvas Visual Preview (R1) | HTML5 Canvas/WebGL 60fps render loop, Keyframe (scale/rotate/pos/alpha), Transition simulation, Scrub Bar | M0 | DONE |
| M2 | Rust Backend Optimization (R2) | Lazy Metadata streaming, Chunked SRT parser (>5k lines), <50MB RAM, <0.1s JSON output, <15% CPU load for 1-3h media | M0 | DONE |
| M3 | Studio Dark Theme UX & Migration Plan (R3) | Commercial 3-column `#121214` Dark Theme UI layout, Step-by-step Tauri+Rust migration blueprint & CapCut JSON engine integration | M1, M2 | DONE |
| M4 | Review, Verification & Forensic Audit | Verification by Reviewer/Challenger subagents and Forensic Integrity Audit by Auditor subagent | M1, M2, M3 | DONE |

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

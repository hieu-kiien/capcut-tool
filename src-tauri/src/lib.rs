pub mod engine;
pub mod commands;

use std::sync::Mutex;
use lru::LruCache;
use engine::LazyMediaProber;
use commands::probe::ProberState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(ProberState {
            prober: LazyMediaProber::new(1000),
        })
        .invoke_handler(tauri::generate_handler![
            commands::probe::probe_media_file,
            commands::srt::parse_srt_file,
            commands::draft::export_capcut_draft,
            commands::sidecar::run_python_hybrid_sidecar,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

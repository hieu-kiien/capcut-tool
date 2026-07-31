use tauri::State;
use crate::engine::probe::{LazyMediaProber, MediaMetadata};

pub struct ProberState {
    pub prober: LazyMediaProber,
}

#[tauri::command]
pub async fn probe_media_file(
    state: State<'_, ProberState>,
    path: String,
) -> Result<MediaMetadata, String> {
    tokio::task::spawn_blocking(move || {
        state.prober.probe_file(&path)
    }).await.map_err(|e| e.to_string())?
}

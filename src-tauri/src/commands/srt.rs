use crate::engine::srt::{SrtParseResult, ZeroCopySrtParser};

#[tauri::command]
pub async fn parse_srt_file(path: String) -> Result<SrtParseResult, String> {
    tokio::task::spawn_blocking(move || {
        ZeroCopySrtParser::parse_file(&path)
    }).await.map_err(|e| e.to_string())?
}

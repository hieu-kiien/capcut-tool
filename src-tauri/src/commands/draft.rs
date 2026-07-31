use crate::engine::draft::{DraftExportParams, DraftExportResult, StreamingCapCutDraftWriter};

#[tauri::command]
pub async fn export_capcut_draft(params: DraftExportParams) -> Result<DraftExportResult, String> {
    tokio::task::spawn_blocking(move || {
        StreamingCapCutDraftWriter::export_draft(&params)
    }).await.map_err(|e| e.to_string())?
}

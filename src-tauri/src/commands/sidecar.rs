use std::process::Command;

#[tauri::command]
pub async fn run_python_hybrid_sidecar(
    script: String,
    args: Vec<String>
) -> Result<String, String> {
    tokio::task::spawn_blocking(move || {
        let mut cmd = Command::new("python");
        cmd.arg(&script);
        for arg in args {
            cmd.arg(arg);
        }

        let output = cmd.output().map_err(|e| format!("Failed to execute python sidecar: {}", e))?;

        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).to_string())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }).await.map_err(|e| e.to_string())?
}

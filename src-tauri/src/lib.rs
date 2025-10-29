use tauri::Manager;
mod grpc_client;

#[tauri::command]
async fn upload_video(file_path: String, file_id: String) -> Result<String, String> {
    let file_data = std::fs::read(&file_path).map_err(|e| e.to_string())?;
    let result = grpc_client::transcribe_video(file_id, file_data)
        .await
        .map_err(|e| e.to_string())?;
    Ok(result)
}

#[tauri::command]
async fn upload_video_bytes(file_id: String, bytes: Vec<u8>) -> Result<String, String> {
    grpc_client::transcribe_video(file_id, bytes)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_temp_path() -> Result<String, String> {
    Ok(std::env::temp_dir().to_string_lossy().to_string())
}

#[tauri::command]
async fn get_transcription(_file_id: String) -> Result<String, String> {
    Ok("Transcription text".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            upload_video,
            upload_video_bytes,
            get_transcription,
            get_temp_path
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
async fn get_file_messages(
    file_id: String,
    limit: i32,
    cursor: Option<String>,
) -> Result<serde_json::Value, String> {
    grpc_client::get_file_messages(file_id, limit, cursor)
        .await
        .map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            upload_video,
            upload_video_bytes,
            get_transcription,
            get_temp_path,
            get_file_messages,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
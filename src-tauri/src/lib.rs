use tauri::Manager;
use tokio::runtime::Runtime;
mod grpc_client;

#[tauri::command]
async fn upload_video(file_path: String, file_id: String) -> Result<String, String> {
    // Read file data
    let file_data = std::fs::read(&file_path).map_err(|e| e.to_string())?;
    
    // Call gRPC server
    let result = grpc_client::transcribe_video(file_id.clone(), file_data)
        .await
        .map_err(|e| e.to_string())?;
    
    // Store transcription result in local storage - probably better
    // TO DO
    
    Ok(result)
}

#[tauri::command]
async fn get_temp_path() -> Result<String, String> {
    let temp_dir = std::env::temp_dir();
    Ok(temp_dir.to_str().unwrap().to_string())
}

#[tauri::command]
async fn get_transcription(file_id: String) -> Result<String, String> {
    // Retrieve from local cache or call gRPC again
    Ok("Transcription text".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            upload_video,
            get_transcription,
            get_temp_path
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
  app_lib::run();
  let _child = std::process::Command::new("python")
    .args(["backend/mcp/transcription_server.py"])
    .spawn()
    .expect("failed to start transcription server");
  // store handle and terminate on app exit (handled in app_lib)
}

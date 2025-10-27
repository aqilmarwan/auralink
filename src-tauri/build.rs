fn main() {
  tonic_build::configure()
      .build_server(false) 
      .build_client(true)
      .compile(
          &["proto/audio_service.proto"],
          &["proto"],
      )
      .unwrap();
  
  tauri_build::build()
}
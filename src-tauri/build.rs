fn main() {
  tonic_build::configure()
      .build_server(false) 
      .build_client(true)
      .compile_protos(  // Changed from compile() to compile_protos()
          &["../proto/audio_service.proto"],  // Added ../ to go up one directory
          &["../proto"],                       // Added ../ to go up one directory
      )
      .unwrap();
  
  tauri_build::build()
}
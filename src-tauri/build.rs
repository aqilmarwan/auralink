fn main() {
  tonic_build::configure()
      .build_server(false) 
      .build_client(true)
      .compile_protos(
          &["../proto/audio_service.proto"],
          &["../proto"],
      )
      .unwrap();

  tauri_build::build()
}
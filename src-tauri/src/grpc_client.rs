use tonic::Request;
use auralink::transcription_service_client::TranscriptionServiceClient;
use auralink::vision_service_client::VisionServiceClient;
use auralink::generation_service_client::GenerationServiceClient;
use auralink::chat_service_client::ChatServiceClient;

pub mod auralink {
    tonic::include_proto!("auralink");
}

#[allow(dead_code)]
pub struct GrpcClients {
    pub transcription: TranscriptionServiceClient<tonic::transport::Channel>,
    pub vision: VisionServiceClient<tonic::transport::Channel>,
    pub generation: GenerationServiceClient<tonic::transport::Channel>,
    #[allow(dead_code)]
    pub chat: ChatServiceClient<tonic::transport::Channel>,
}

impl GrpcClients {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        // Each service runs on a different port - create separate channels with short connect timeout
        let transcription_channel = tonic::transport::Channel::from_static("http://127.0.0.1:50051")
            .connect_timeout(std::time::Duration::from_secs(2))
            .connect()
            .await?;
        let vision_channel = tonic::transport::Channel::from_static("http://127.0.0.1:50052")
            .connect_timeout(std::time::Duration::from_secs(2))
            .connect()
            .await?;
        let generation_channel = tonic::transport::Channel::from_static("http://127.0.0.1:50053")
            .connect_timeout(std::time::Duration::from_secs(2))
            .connect()
            .await?;
        // Chat service shares port with transcription (or can be separate)
        let chat_channel = transcription_channel.clone();
        
        let transcription = TranscriptionServiceClient::new(transcription_channel)
            .max_decoding_message_size(50 * 1024 * 1024)
            .max_encoding_message_size(50 * 1024 * 1024);
        let vision = VisionServiceClient::new(vision_channel)
            .max_decoding_message_size(50 * 1024 * 1024)
            .max_encoding_message_size(50 * 1024 * 1024);
        let generation = GenerationServiceClient::new(generation_channel)
            .max_decoding_message_size(50 * 1024 * 1024)
            .max_encoding_message_size(50 * 1024 * 1024);
        let chat = ChatServiceClient::new(chat_channel)
            .max_decoding_message_size(20 * 1024 * 1024)
            .max_encoding_message_size(20 * 1024 * 1024);

        Ok(Self {
            transcription,
            vision,
            generation,
            chat,
        })
    }
}

pub async fn transcribe_video(file_id: String, audio_data: Vec<u8>) -> Result<String, String> {
    let mut clients = GrpcClients::new().await.map_err(|e| e.to_string())?;
    
    let request = Request::new(auralink::TranscribeRequest {
        file_id,
        audio_data,
        format: "mp4".to_string(),
    });
    
    let response = clients.transcription
        .transcribe_video(request)
        .await
        .map_err(|e| e.to_string())?;
    
    Ok(response.into_inner().text)
}

pub async fn vision_detect_objects(image_data: Vec<u8>) -> Result<String, String> {
    let mut clients = GrpcClients::new().await.map_err(|e| e.to_string())?;

    let request = Request::new(auralink::ImageRequest {
        file_id: "".to_string(),
        image_data,
        frame_number: 0,
    });

    let response = clients
        .vision
        .detect_objects(request)
        .await
        .map_err(|e| e.to_string())?;

    let inner = response.into_inner();
    let caption = inner.caption;
    let count = inner.objects.len();
    let top = inner
        .objects
        .into_iter()
        .take(5)
        .map(|o| format!("{} ({:.2})", o.label, o.confidence))
        .collect::<Vec<_>>()
        .join(", ");
    Ok(format!(
        "Detected {} object(s): {}. Caption: {}",
        count, top, caption
    ))
}

pub async fn vision_identify_graphs(image_data: Vec<u8>) -> Result<String, String> {
    let mut clients = GrpcClients::new().await.map_err(|e| e.to_string())?;

    let request = Request::new(auralink::ImageRequest {
        file_id: "".to_string(),
        image_data,
        frame_number: 0,
    });

    let response = clients
        .vision
        .identify_graphs(request)
        .await
        .map_err(|e| e.to_string())?;

    let inner = response.into_inner();
    if inner.graphs.is_empty() {
        Ok(format!("No graphs detected. {}", inner.description))
    } else {
        let kinds = inner
            .graphs
            .into_iter()
            .map(|g| g.r#type)
            .collect::<Vec<_>>()
            .join(", ");
        Ok(format!("Graphs detected: {}. {}", kinds, inner.description))
    }
}

pub async fn generation_generate_pdf(
    file_id: String,
    key_points: Vec<String>,
) -> Result<String, String> {
    let mut clients = GrpcClients::new().await.map_err(|e| e.to_string())?;

    let request = Request::new(auralink::GenerateRequest {
        file_id,
        key_points,
        output_format: "pdf".to_string(),
    });

    let response = clients
        .generation
        .generate_pdf(request)
        .await
        .map_err(|e| e.to_string())?;
    let inner = response.into_inner();
    if inner.success {
        Ok(format!("PDF generated at {}", inner.output_file_path))
    } else {
        Err(inner.error_message)
    }
}

pub async fn generation_generate_powerpoint(
    file_id: String,
    key_points: Vec<String>,
) -> Result<String, String> {
    let mut clients = GrpcClients::new().await.map_err(|e| e.to_string())?;

    let request = Request::new(auralink::GenerateRequest {
        file_id,
        key_points,
        output_format: "ppt".to_string(),
    });

    let response = clients
        .generation
        .generate_power_point(request)
        .await
        .map_err(|e| e.to_string())?;
    let inner = response.into_inner();
    if inner.success {
        Ok(format!("PowerPoint generated at {}", inner.output_file_path))
    } else {
        Err(inner.error_message)
    }
}

pub async fn generation_generate_summary(
    file_id: String,
    message_limit: i32,
) -> Result<String, String> {
    let mut clients = GrpcClients::new().await.map_err(|e| e.to_string())?;

    let request = Request::new(auralink::ChatHistoryRequest { file_id, message_limit });

    let response = clients
        .generation
        .generate_summary(request)
        .await
        .map_err(|e| e.to_string())?;
    let inner = response.into_inner();
    Ok(inner.summary)
}

#[allow(dead_code)]
pub async fn get_file_messages(
    file_id: String,
    limit: i32,
    cursor: Option<String>,
) -> Result<serde_json::Value, String> {
    let mut clients = GrpcClients::new().await.map_err(|e| e.to_string())?;
    
    let request = Request::new(auralink::GetFileMessagesRequest {
        file_id,
        limit,
        cursor,
    });
    
    let response = clients
        .chat
        .get_file_messages(request)
        .await
        .map_err(|e| e.to_string())?;
    
    let inner = response.into_inner();
    let messages: Vec<serde_json::Value> = inner
        .messages
        .into_iter()
        .map(|msg| {
            serde_json::json!({
                "id": msg.id,
                "text": msg.text,
                "isUserMessage": msg.is_user_message,
                "createdAt": msg.created_at,
            })
        })
        .collect();
    
    Ok(serde_json::json!({
        "messages": messages,
        "nextCursor": inner.next_cursor,
    }))
}
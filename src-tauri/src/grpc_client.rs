use tonic::Request;
use auralink::transcription_service_client::TranscriptionServiceClient;
use auralink::vision_service_client::VisionServiceClient;
use auralink::generation_service_client::GenerationServiceClient;
use auralink::chat_service_client::ChatServiceClient;

pub mod auralink {
    tonic::include_proto!("auralink");
}

pub struct GrpcClients {
    pub transcription: TranscriptionServiceClient<tonic::transport::Channel>,
    pub vision: VisionServiceClient<tonic::transport::Channel>,
    pub generation: GenerationServiceClient<tonic::transport::Channel>,
    pub chat: ChatServiceClient<tonic::transport::Channel>,
}

impl GrpcClients {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let channel = tonic::transport::Channel::from_static("http://[::1]:50051")
            .connect()
            .await?;
        
        Ok(Self {
            transcription: TranscriptionServiceClient::new(channel.clone()),
            vision: VisionServiceClient::new(channel.clone()),
            generation: GenerationServiceClient::new(channel),
            chat: ChatServiceClient::new(channel),
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
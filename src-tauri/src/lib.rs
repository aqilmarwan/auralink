mod grpc_client;
mod db;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};
use std::net::{TcpStream, SocketAddr};
use std::io::{BufRead, BufReader};
use std::sync::{Arc, Mutex};
use tauri::Manager;
use tauri::WindowEvent;

struct AgentHandles(pub Arc<Mutex<Vec<Child>>>);
fn friendly_sentence(raw: &str) -> String {
    let lower = raw.to_lowercase();
    // Remove common labels and reformulate
    if lower.starts_with("transcription:") {
        let msg = raw.splitn(2, ':').nth(1).unwrap_or("").trim();
        if msg.is_empty() { return "I attempted transcription.".to_string(); }
        return format!("Regarding transcription, {}.", msg);
    }
    if lower.starts_with("objects:") {
        // Try to pull caption snippet
        let without = raw.splitn(2, ':').nth(1).unwrap_or("").trim();
        if let Some(idx) = without.find("Caption:") {
            let cap = without[idx+8..].trim();
            if !cap.is_empty() { return format!("From a video frame, {}.", cap); }
        }
        return format!("From a video frame, {}.", without);
    }
    if lower.starts_with("graphs:") {
        let without = raw.splitn(2, ':').nth(1).unwrap_or("").trim();
        return format!("On charts and graphs, {}.", without);
    }
    if lower.contains("generated at ") {
        // Try to extract local file path and present a nice markdown link
        // Expected formats from generation client:
        //   "PowerPoint generated at {path}"
        //   "PDF generated at {path}"
        let mut path_part: Option<&str> = None;
        if let Some(idx) = lower.find("generated at ") {
            // Use the original raw string to preserve exact path casing
            let start = idx + "generated at ".len();
            if start <= raw.len() {
                let p = &raw[start..].trim();
                if !p.is_empty() { path_part = Some(p); }
            }
        }
        if lower.contains("powerpoint") {
            if let Some(path) = path_part {
                // Render a clickable link with a visible path
                // WebView usually supports file:// links
                let link = format!("file://{}", path);
                return format!("PowerPoint generated. [Open file]({})\nPath: `{}`", link, path);
            }
            return "PowerPoint generated and saved locally.".to_string();
        }
        if lower.contains("pdf") {
            if let Some(path) = path_part {
                let link = format!("file://{}", path);
                return format!("PDF generated. [Open file]({})\nPath: `{}`", link, path);
            }
            return "PDF generated and saved locally.".to_string();
        }
    }
    raw.to_string()
}

fn clamp_len(s: String, max: usize) -> String {
    if s.len() <= max { return s; }
    let mut t = s;
    t.truncate(max);
    t.push_str("…");
    t
}

#[derive(Debug)]
struct IntentScore {
    transcribe: u8,
    objects: u8,
    graphs: u8,
    ppt: u8,
    pdf: u8,
    summary: u8,
}

impl IntentScore {
    fn from_message(msg: &str) -> Self {
        let lower = msg.to_lowercase();
        let mut score = IntentScore {
            transcribe: 0,
            objects: 0,
            graphs: 0,
            ppt: 0,
            pdf: 0,
            summary: 0,
        };

        // Strong signals (high confidence)
        if lower.contains("transcribe the video") || lower.contains("transcript of") {
            score.transcribe = 10;
        } else if lower.contains("transcribe") || lower.contains("what is said") || lower.contains("what they say") {
            score.transcribe = 7;
        }

        if lower.contains("what objects") || lower.contains("detect objects") || lower.contains("identify objects") {
            score.objects = 10;
        } else if lower.contains("object") || lower.contains("what is shown") || lower.contains("what's in the") {
            score.objects = 6;
        }

        if lower.contains("are there") && (lower.contains("graph") || lower.contains("chart")) {
            score.graphs = 10;
        } else if lower.contains("graph") || lower.contains("chart") || lower.contains("diagram") {
            score.graphs = 7;
        }

        if lower.contains("create a powerpoint") || lower.contains("generate powerpoint") || lower.contains("make a ppt") {
            score.ppt = 10;
        } else if lower.contains("powerpoint") || lower.contains("ppt") || lower.contains("presentation") {
            score.ppt = 6;
        }

        if (lower.contains("summarize") || lower.contains("summary")) && lower.contains("pdf") {
            score.summary = 10;
            score.pdf = 10;
        } else if lower.contains("generate pdf") || lower.contains("create pdf") {
            score.pdf = 10;
        } else if lower.contains("pdf") {
            score.pdf = 5;
        }

        if lower.contains("summarize") || lower.contains("summary of") || lower.contains("recap") {
            score.summary = 8;
        }

        score
    }

    fn is_ambiguous(&self) -> bool {
        let low_threshold = 6;
        let active_count = [
            self.transcribe > 0 && self.transcribe < low_threshold,
            self.objects > 0 && self.objects < low_threshold,
            self.graphs > 0 && self.graphs < low_threshold,
            self.ppt > 0 && self.ppt < low_threshold,
            self.pdf > 0 && self.pdf < low_threshold,
            self.summary > 0 && self.summary < low_threshold,
        ]
        .iter()
        .filter(|&&x| x)
        .count();

        // Ambiguous if multiple weak signals or any signal is below threshold
        active_count >= 2 || (active_count == 1 && self.max_score() < low_threshold)
    }

    fn max_score(&self) -> u8 {
        *[self.transcribe, self.objects, self.graphs, self.ppt, self.pdf, self.summary]
            .iter()
            .max()
            .unwrap_or(&0)
    }

    fn has_any_intent(&self) -> bool {
        self.max_score() > 0
    }

    fn get_clarification_message(&self) -> String {
        let mut options = Vec::new();

        if self.transcribe > 0 {
            options.push("transcribe the audio");
        }
        if self.objects > 0 {
            options.push("detect objects in the video");
        }
        if self.graphs > 0 {
            options.push("identify charts or graphs");
        }
        if self.ppt > 0 {
            options.push("create a PowerPoint presentation");
        }
        if self.pdf > 0 && self.summary == 0 {
            options.push("generate a PDF document");
        }
        if self.summary > 0 {
            options.push("summarize our conversation");
        }

        if options.is_empty() {
            return "I'm not sure what you'd like me to do. Could you clarify? For example:\n\
                    - \"Transcribe the video\"\n\
                    - \"What objects are shown?\"\n\
                    - \"Create a PowerPoint\"\n\
                    - \"Summarize our discussion\"".to_string();
        }

        if options.len() == 1 {
            return format!("Did you mean: {}? If so, please confirm or provide more details.", options[0]);
        }

        let formatted = options
            .iter()
            .enumerate()
            .map(|(i, opt)| format!("{}. {}", i + 1, opt))
            .collect::<Vec<_>>()
            .join("\n");

        format!("I detected multiple possible actions. Which would you like me to do?\n{}\n\nPlease specify by number or rephrase your request.", formatted)
    }
}

fn format_conversational_response(_file_id: &str, _user_msg: &str, parts: &[String]) -> String {
    if parts.is_empty() {
        return "Acknowledged.".to_string();
    }
    // Attempt to extract a short caption if available from vision output
    let mut caption_line: Option<String> = None;
    for p in parts {
        if p.to_lowercase().starts_with("objects:") {
            if let Some(idx) = p.find("Caption:") {
                caption_line = Some(p[idx..].replacen("Caption:", "", 1).trim().to_string());
                break;
            }
        }
    }
    let intro = if let Some(c) = caption_line {
        format!("Here’s what I found about this video: {}", c)
    } else {
        "Here’s what I found about this video:".to_string()
    };
    // Filter out noisy/unhelpful lines
    let cleaned: Vec<String> = parts
        .iter()
        .map(|p| friendly_sentence(p))
        .filter(|p| !p.to_lowercase().contains("unavailable"))
        .collect();
    // Dynamic length: allocate budget by number of items (aim for ~600 chars total)
    let max_total = 600usize;
    let per_item = std::cmp::max(140usize, max_total.saturating_div(std::cmp::max(1, cleaned.len())));
    let bullets = cleaned
        .into_iter()
        .map(|p| clamp_len(p, per_item))
        .map(|p| format!("- {}", p))
        .collect::<Vec<_>>()
        .join("\n");
    let outro = "I can analyze more frames or generate materials if you’d like.";
    format!("{}\n{}\n{}", intro, bullets, outro)
}

fn resolve_script(rel: &str) -> std::path::PathBuf {
    // Try current working directory first (dev usually runs from repo root)
    let cwd = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
    let p1 = cwd.join(rel);
    if p1.exists() { return p1; }

    // Try project root calculated from src-tauri manifest dir
    let tauri_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let project_root = tauri_dir.parent().unwrap_or(&tauri_dir);
    let p2 = project_root.join(rel);
    if p2.exists() { return p2; }

    // Fall back to returning first candidate (even if missing)
    p1
}

fn ensure_dir(path: &std::path::Path) {
    let _ = std::fs::create_dir_all(path);
}

fn generate_python_protos() {
    // Generate Python gRPC stubs into backend/generated
    let cwd = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
    let gen_dir = cwd.join("backend/generated");
    ensure_dir(&gen_dir);
    let proto_path = cwd.join("proto/audio_service.proto");
    if !proto_path.exists() { return; }

    let status = Command::new("python3")
        .args([
            "-m",
            "grpc_tools.protoc",
            "-Iproto",
            "--python_out=backend/generated",
            "--grpc_python_out=backend/generated",
            "proto/audio_service.proto",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .status();
    if let Ok(s) = status {
        if !s.success() {
            println!("[Tauri] Warning: failed to generate Python gRPC stubs (grpc_tools not installed?)");
        }
    }
}

fn wait_for_port(port: u16, timeout_secs: u64) -> bool {
    let deadline = Instant::now() + Duration::from_secs(timeout_secs);
    let addr: SocketAddr = format!("127.0.0.1:{}", port).parse().unwrap();
    while Instant::now() < deadline {
        if TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    false
}

fn spawn_python_agent(script_rel: &str, args: &[&str]) -> Option<Child> {
    let script = resolve_script(script_rel);
    if !script.exists() { 
        println!("[Tauri] Agent script not found: {}", script.to_string_lossy());
        return None; 
    }
    let mut cmd = Command::new("python3");
    // Ensure Python can import generated stubs and backend package
    let cwd = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
    let gen_dir = cwd.join("backend/generated");
    let backend_dir = cwd.join("backend");
    let existing_pythonpath = std::env::var("PYTHONPATH").unwrap_or_default();
    let new_pythonpath = if existing_pythonpath.is_empty() {
        format!("{}:{}", gen_dir.to_string_lossy(), backend_dir.to_string_lossy())
    } else {
        format!("{}:{}:{}", existing_pythonpath, gen_dir.to_string_lossy(), backend_dir.to_string_lossy())
    };
    cmd.env("PYTHONPATH", new_pythonpath);
    let mut child = cmd
        .arg(script)
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .ok()?;

    // Stream stdout/stderr to console for easier debugging
    if let Some(out) = child.stdout.take() {
        let reader = BufReader::new(out);
        std::thread::spawn(move || {
            for line in reader.lines() {
                if let Ok(l) = line { println!("[agent stdout] {}", l); }
            }
        });
    }
    if let Some(err) = child.stderr.take() {
        let reader = BufReader::new(err);
        std::thread::spawn(move || {
            for line in reader.lines() {
                if let Ok(l) = line { eprintln!("[agent stderr] {}", l); }
            }
        });
    }

    Some(child)
}

fn start_agents() -> Vec<Child> {
    let mut children = Vec::new();
    // Generate stubs first so servers can import auralink_pb2*
    generate_python_protos();
    // Start transcription, vision, generation servers if scripts exist
    // Models will load automatically on startup when servers are instantiated
    if let Some(c) = spawn_python_agent("backend/mcp/transcription_server.py", &["--port", "50051", "--model", "base"]) { 
        println!("[Tauri] Started transcription agent on port 50051");
        children.push(c); 
    }
    if let Some(c) = spawn_python_agent("backend/mcp/vision_server.py", &["--port", "50052"]) { 
        println!("[Tauri] Started vision agent on port 50052");
        children.push(c); 
    }
    if let Some(c) = spawn_python_agent("backend/mcp/generation_server.py", &["--port", "50053"]) { 
        println!("[Tauri] Started generation agent on port 50053");
        children.push(c); 
    }
    // Wait briefly for ports to be ready to avoid initial transport errors
    let mut ready_count = 0usize;
    for (name, port) in [("transcription",50051u16),("vision",50052u16),("generation",50053u16)] {
        if wait_for_port(port, 20) {
            println!("[Tauri] {} agent is accepting connections on {}", name, port);
            ready_count += 1;
        } else {
            println!("[Tauri] Warning: {} agent did not open port {} in time", name, port);
        }
    }
    println!("[Tauri] Launched {} process(es); {} ready", children.len(), ready_count);
    children
}

#[tauri::command]
async fn save_message(file_id: String, text: String, is_user: bool) -> Result<(), String> {
    let id = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();
    db::insert_message(&id, &file_id, &text, is_user, &now).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_messages(file_id: String, limit: i32, cursor: Option<String>)
  -> Result<serde_json::Value, String> {
    let page = db::list_messages(&file_id, limit as i64, cursor.as_deref())
        .map_err(|e| e.to_string())?;
    Ok(serde_json::json!({
      "messages": page.messages,
      "nextCursor": page.next_cursor
    }))
}

#[tauri::command]
async fn send_message(file_id: String, message: String) -> Result<String, String> {
    // persist user message
    save_message(file_id.clone(), message.clone(), true).await?;
    
    // Check if user is responding to a clarification with a number
    let trimmed = message.trim();
    let is_numeric_response = trimmed.len() == 1 && trimmed.chars().all(|c| c.is_numeric());
    
    // Map numeric responses to explicit intents
    let resolved_message = if is_numeric_response {
        match trimmed {
            "1" => "transcribe the video".to_string(),
            "2" => "what objects are shown in the video".to_string(),
            "3" => "are there any graphs or charts".to_string(),
            "4" => "create a powerpoint presentation".to_string(),
            "5" => "generate a pdf document".to_string(),
            "6" => "summarize our conversation".to_string(),
            _ => message.clone(),
        }
    } else {
        message.clone()
    };
    
    // Score the intent with confidence levels
    let intent = IntentScore::from_message(&resolved_message);
    
    // Check if the query is ambiguous or low-confidence
    if intent.is_ambiguous() {
        let clarification = intent.get_clarification_message();
        save_message(file_id.clone(), clarification.clone(), false).await?;
        return Ok(clarification);
    }
    
    // If no clear intent detected, ask for clarification
    if !intent.has_any_intent() {
        let clarification = "I'm not sure what you'd like me to do with this video. Could you provide more details? For example:\n\
            - \"Transcribe the video\"\n\
            - \"What objects are shown in the video?\"\n\
            - \"Are there any graphs?\"\n\
            - \"Create a PowerPoint with key points\"\n\
            - \"Summarize our discussion and generate a PDF\"".to_string();
        save_message(file_id.clone(), clarification.clone(), false).await?;
        return Ok(clarification);
    }
    
    // High-confidence routing based on scores (threshold >= 7 for auto-execution)
    let confidence_threshold = 7u8;
    let wants_transcribe = intent.transcribe >= confidence_threshold;
    let wants_objects = intent.objects >= confidence_threshold;
    let wants_graphs = intent.graphs >= confidence_threshold;
    let wants_ppt = intent.ppt >= confidence_threshold;
    let wants_summary_pdf = intent.summary >= confidence_threshold && intent.pdf >= confidence_threshold;
    let wants_pdf = !wants_summary_pdf && intent.pdf >= confidence_threshold;

    // helper: small retry for transient transport errors
    fn sanitize_err(err: String) -> String {
        let lower = err.to_lowercase();
        // Common connectivity failures
        if lower.contains("transport") || lower.contains("unavailable") || lower.contains("deadline") {
            return "agent unavailable".to_string();
        }
        // Message too large from gRPC (e.g., sending whole video bytes)
        if lower.contains("resourceexhausted") || lower.contains("message larger than max") {
            return "request too large for a single call; try a shorter clip or let me extract audio automatically".to_string();
        }
        // Hide verbose metadata noise if present
        if let Some(idx) = lower.find("metadata:") {
            let trimmed = &err[..idx];
            return format!("{}", trimmed.trim());
        }
        // Generic friendly fallback
        "couldn’t complete this right now; please try again".to_string()
    }

    async fn retry<F, Fut>(mut f: F) -> String
    where
        F: FnMut() -> Fut,
        Fut: std::future::Future<Output = Result<String, String>>,
    {
        let mut last = String::new();
        for _ in 0..2 {
            match f().await {
                Ok(s) => return s,
                Err(e) => { last = sanitize_err(e); tokio::time::sleep(std::time::Duration::from_millis(350)).await; }
            }
        }
        format!("{}", last)
    }

    let mut parts: Vec<String> = Vec::new();

    // Transcription
    if wants_transcribe {
        let part = match db::get_file_path(&file_id) {
            Ok(Some(path)) => {
                match std::fs::read(&path) {
                    Ok(bytes) => retry(|| grpc_client::transcribe_video(file_id.clone(), bytes.clone())).await,
                    Err(e) => format!("Failed to read file: {}", e),
                }
            }
            Ok(None) => "File not found for transcription".to_string(),
            Err(e) => format!("Lookup error: {}", e),
        };
        parts.push(format!("Transcription: {}", part));
    }

    // Prepare a single thumbnail for all vision requests
    let mut thumb_bytes: Option<Vec<u8>> = None;
    if wants_objects || wants_graphs {
        match generate_thumbnail(file_id.clone()).await {
            Ok(thumb_path) => match std::fs::read(&thumb_path) {
                Ok(b) => { thumb_bytes = Some(b); }
                Err(e) => parts.push(format!("Failed to read thumbnail: {}", e)),
            },
            Err(e) => parts.push(format!("Failed to generate thumbnail: {}", e)),
        }
    }

    if wants_objects {
        let part = if let Some(b) = &thumb_bytes { retry(|| grpc_client::vision_detect_objects(b.clone())).await } else { "Vision unavailable".to_string() };
        parts.push(format!("Objects: {}", part));
    }

    if wants_graphs {
        let part = if let Some(b) = &thumb_bytes { retry(|| grpc_client::vision_identify_graphs(b.clone())).await } else { "Vision unavailable".to_string() };
        parts.push(format!("Graphs: {}", part));
    }

    // Generation flows
    if wants_ppt {
        let part = retry(|| grpc_client::generation_generate_powerpoint(file_id.clone(), vec![])).await;
        parts.push(format!("PowerPoint: {}", part));
    }
    if wants_summary_pdf {
        let summary = retry(|| grpc_client::generation_generate_summary(file_id.clone(), 100)).await;
        let pdf = retry(|| grpc_client::generation_generate_pdf(file_id.clone(), vec![])).await;
        parts.push(format!("Summary: {}", summary));
        parts.push(format!("PDF: {}", pdf));
    } else if wants_pdf {
        let pdf = retry(|| grpc_client::generation_generate_pdf(file_id.clone(), vec![])).await;
        parts.push(format!("PDF: {}", pdf));
    }

    let ai_text = format_conversational_response(&file_id, &message, &parts);
    // persist AI reply
    save_message(file_id.clone(), ai_text.to_string(), false).await?;
    Ok(ai_text.to_string())
}

#[tauri::command]
fn get_temp_path() -> Result<String, String> {
    Ok(std::env::temp_dir()
        .to_string_lossy()
        .to_string())
}

#[tauri::command]
async fn upload_video_bytes(file_id: String, bytes: Vec<u8>) -> Result<String, String> {
    // Fire-and-forget transcription; do not fail UI if backend is down
    let _ = grpc_client::transcribe_video(file_id.clone(), bytes).await;
    Ok("ok".to_string())
}

#[tauri::command]
async fn auth_callback() -> Result<serde_json::Value, String> {
    // Placeholder: perform any local setup if needed (e.g., creating a user row)
    Ok(serde_json::json!({ "success": true }))
}

#[tauri::command]
async fn get_app_data_dir() -> Result<String, String> {
    Ok(db::db_path()
        .parent()
        .unwrap_or(std::path::Path::new("."))
        .to_string_lossy()
        .to_string())
}

#[tauri::command]
async fn register_file(file_id: String, path: String) -> Result<(), String> {
    let now = chrono::Utc::now().to_rfc3339();
    let name = std::path::Path::new(&path)
        .file_name()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();
    db::insert_file(&file_id, &name, &path, &now).map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_file_path(file_id: String) -> Result<Option<String>, String> {
    db::get_file_path(&file_id).map_err(|e| e.to_string())
}

#[allow(non_snake_case)]
#[derive(serde::Serialize)]
struct FileItem { id: String, name: String, path: String, thumbPath: Option<String>, createdAt: String }

#[tauri::command]
async fn list_files() -> Result<Vec<FileItem>, String> {
    let rows = db::list_files().map_err(|e| e.to_string())?;
    let items = rows
        .into_iter()
        .map(|r| FileItem {
            id: r.id.clone(),
            name: r.name.unwrap_or_else(|| std::path::Path::new(&r.path)
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string()),
            path: r.path,
            thumbPath: r.thumb_path,
            createdAt: r.created_at,
        })
        .collect();
    Ok(items)
}

#[tauri::command]
async fn delete_file(id: String) -> Result<(), String> {
    // try to remove the actual file if it exists
    if let Ok(Some(path)) = db::get_file_path(&id) { let _ = std::fs::remove_file(path); }
    db::delete_file(&id).map_err(|e| e.to_string())
}

#[tauri::command]
async fn save_file_bytes(file_id: String, ext: String, bytes: Vec<u8>, name: Option<String>) -> Result<String, String> {
    // Determine app data directory (same as DB)
    let dir = db::db_path()
        .parent()
        .unwrap_or(std::path::Path::new("."))
        .to_path_buf();
    let _ = std::fs::create_dir_all(&dir);
    let path = dir.join(format!("{}.{}", file_id, ext));
    std::fs::write(&path, &bytes).map_err(|e| e.to_string())?;
    let now = chrono::Utc::now().to_rfc3339();
    let file_name = name.unwrap_or_else(|| format!("{}.{}", file_id, ext));
    db::insert_file(&file_id, &file_name, &path.to_string_lossy(), &now).map_err(|e| e.to_string())?;
    // Try to generate a thumbnail immediately (best effort)
    if let Ok(p) = generate_thumbnail(file_id.clone()).await { let _ = db::set_file_thumb(&file_id, &p); }
    Ok(path.to_string_lossy().to_string())
}

#[tauri::command]
async fn read_file_bytes(file_id: String) -> Result<Vec<u8>, String> {
    match db::get_file_path(&file_id) {
        Ok(Some(path)) => std::fs::read(path).map_err(|e| e.to_string()),
        Ok(None) => Err("File not found".to_string()),
        Err(e) => Err(e.to_string()),
    }
}

#[tauri::command]
async fn generate_thumbnail(file_id: String) -> Result<String, String> {
    // Find input path
    let in_path = db::get_file_path(&file_id).map_err(|e| e.to_string())?
        .ok_or_else(|| "File not found".to_string())?;

    // Ensure output directory
    let db_path = db::db_path();
    let base_dir = db_path.parent().unwrap_or(std::path::Path::new(".")).to_path_buf();
    let thumbs_dir = base_dir.join("thumbs");
    std::fs::create_dir_all(&thumbs_dir).map_err(|e| e.to_string())?;
    let out_path = thumbs_dir.join(format!("{}.jpg", file_id));

    // Build ffmpeg command: capture at 1s and scale
    let output = Command::new("ffmpeg")
        .args(["-y", "-ss", "00:00:01", "-i", &in_path, "-frames:v", "1", "-vf", "scale=320:-1", out_path.to_string_lossy().as_ref()])
        .output()
        .map_err(|e| format!("Failed to run ffmpeg: {}", e))?;

    if !output.status.success() {
        let mut msg = String::from("ffmpeg failed to generate thumbnail");
        if !output.stderr.is_empty() {
            msg.push_str(": ");
            msg.push_str(&String::from_utf8_lossy(&output.stderr));
        }
        return Err(msg);
    }

    Ok(out_path.to_string_lossy().to_string())
}

#[tauri::command]
async fn backfill_thumbnails() -> Result<usize, String> {
    let rows = db::list_files().map_err(|e| e.to_string())?;
    let mut updated = 0usize;
    for r in rows {
        if r.thumb_path.is_some() { continue; }
        // Skip if source file is missing
        if !std::path::Path::new(&r.path).exists() { continue; }
        match generate_thumbnail(r.id.clone()).await {
            Ok(p) => {
                let _ = db::set_file_thumb(&r.id, &p);
                updated += 1;
            }
            Err(_) => {
                // ignore and continue; we want best-effort
            }
        }
    }
    Ok(updated)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    db::init().expect("db init failed");
    let handles = AgentHandles(Arc::new(Mutex::new(start_agents())));
    tauri::Builder::default()
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_log::Builder::default().build())
        .manage(handles)
        .on_window_event(|app, event| {
            if let WindowEvent::CloseRequested { .. } = event { 
                {
                    let arc = app.state::<AgentHandles>().0.clone();
                    let lock_result = arc.lock();
                    if let Ok(mut vec) = lock_result {
                        for child in vec.iter_mut() {
                            let _ = child.kill();
                        }
                        vec.clear();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            save_message,
            get_messages,
            send_message,
            get_temp_path,
            upload_video_bytes,
            auth_callback,
            get_app_data_dir,
            register_file,
            get_file_path,
            list_files,
            delete_file,
            save_file_bytes,
            read_file_bytes
            ,generate_thumbnail
            ,backfill_thumbnails
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
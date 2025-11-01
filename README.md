<p align="center">
  <img src="public/trace.svg" alt="Auralink" width="250" height=auto />
</p>

<div align="center">
  <a href="https://www.python.org/"><img alt="Typescript" src="https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white" /></a>
  <a href="https://www.typescriptlang.org/"><img alt="Python" src="https://img.shields.io/badge/python-3670A0?style=flat&logo=python&logoColor=white" /></a>
  <a href="https://rust-lang.org/"><img alt="Rust" src="https://img.shields.io/badge/Rust-000000?logo=rust&logoColor=white" /></a>
  <a href="https://github.com/aqilmarwan/auralink/graphs/contributors"><img alt="Contributors" src="https://img.shields.io/github/contributors/aqilmarwan/auralink?color=blue" /></a>
  <a href="https://github.com/aqilmarwan/auralink/commits"><img alt="Last Commit" src="https://img.shields.io/github/last-commit/aqilmarwan/auralink?color=brightgreen" /></a>
  <a href="https://github.com/aqilmarwan/auralink/issues"><img alt="Open Issues" src="https://img.shields.io/github/issues/aqilmarwan/auralink?color=brightgreen&label=issues" /></a>
  <img alt="License" src="https://img.shields.io/badge/license-Proprietary-lightgrey" />
  <a href="https://github.com/aqilmarwan/auralink/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/aqilmarwan/auralink?style=flat&color=blue" /></a>
  <a href="https://github.com/aqilmarwan/auralink/network/members"><img alt="Forks" src="https://img.shields.io/github/forks/aqilmarwan/auralink?style=flat&color=blue" /></a>

  <a> Modern local AI assistant for video understanding and document generation. Auralink pairs a sleek Next.js UI with a Rust (Tauri) app and Python micro-agents over gRPC for transcription, vision analysis, and content generation (PDF/PPT). <a>
</div>

> [!NOTE]
> Development has stopped indefinitely!

> [!WARNING]
> Auralink is currently in the early stages of development and is not yet ready for daily use!

<p align="center">
  <img src="public/ss.png" alt="Auralink UI" width="1020" />
</p>

## Features

- **Chat Workflow**: Ask questions about a video or request outcomes (e.g., “Create a PowerPoint”).
- **Local Agents**:
  - Transcription (audio → text).
  - Vision (objects, graphs/plots, caption).
  - Generation (summary, PDF, PowerPoint).
- **Fast UI**: Smooth, bottom-up chronological chat with optimistic updates and typing animation.
- **Local persistence**: SQLite (via rusqlite) stores files and chat history locally.

## Architecture

```
Next.js (UI)  ──invoke──▶  Tauri (Rust)  ──gRPC──▶  Python agents
  - Chat UI                 - Commands       - transcription_server.py :50051
  - Upload UI               - SQLite DB      - vision_server.py       :50052
  - File list               - ffmpeg/thumbs  - generation_server.py   :50053
```

- UI: `src/` (Next.js 14, React 18, Tailwind). Chat components in `src/components/chat/*`.
- Desktop shell: `src-tauri/` (Rust, Tauri 2). Exposes commands with `#[tauri::command]` in `src-tauri/src/lib.rs`.
- Agents: `backend/mcp/*.py` (Python, gRPC servers). Protos in `proto/audio_service.proto`. Python stubs generated to `backend/generated/`.

### Data Flow (chat)

1. User submits a prompt in `ChatInput.tsx`.
2. Frontend invokes `send_message` (Tauri) → `src-tauri/src/lib.rs`.
3. Rust persists the user message, scores intent, and calls agents via gRPC as needed.
4. Agent responses are post-processed into friendly text and saved as assistant messages.
5. Frontend invalidates the messages query; UI displays messages in chronological order. Assistant responses appear immediately after the user’s prompt.

### Agents

- Transcription: `backend/mcp/transcription_server.py` (gRPC :50051)
- Vision: `backend/mcp/vision_server.py` (gRPC :50052)
- Generation: `backend/mcp/generation_server.py` (gRPC :50053)

Rust auto-generates Python gRPC stubs when the app starts (best effort) and launches agents. It also waits for ports to be ready to reduce initial transport errors.

## Functional Requirements

- Users can upload or register video files and see them listed on dashboard.
- Users can chat about a selected file; messages are persisted locally.
- The system can:
  - Transcribe audio from the video.
  - Detect objects and identify graphs from a representative frame.
  - Generate summaries of the chat/file.
  - Produce a PDF and/or a PowerPoint.
- When generating a file (PDF/PPT), the assistant message includes a clickable `file://` hyperlink with the full local path for quick access.

## Tech Stack

- UI: Next.js 14, React 18, Tailwind, React Query, React Markdown
- Desktop: Tauri 2 (Rust), rusqlite, tonic (gRPC client)
- Agents: Python 3, gRPC, Whisper, OpenVINO/ONNX Runtime, MoviePy, NumPy
- Media tooling: ffmpeg (required on host)

## Getting Started

### Prerequisites

- Node.js 18+ and pnpm/npm
- Rust toolchain and Tauri prerequisites (see Tauri docs for your OS)
- Python 3.11+

### Install dependencies

```bash
npm install
```

Install Python deps for agents:

```bash
python3 -m venv .venv
source .venv/bin/activate 
pip install -r backend/requirements.txt
```

### Run in development (desktop)

This starts Next.js in dev and runs the Tauri app which launches agents.

```bash
npm run tauri dev
```

Alternatively, you can run the web dev server only (without desktop shell):

```bash
npm run dev
```

Note: Local agents and Tauri commands are expected; web-only mode is limited.

## Usage Guide

1. Open the app and upload a video.
2. Open the chat for a file and ask a question or request an action.
3. For generation tasks (PDF/PPT), the assistant will reply with a link like:

   - `PowerPoint generated. [Open file](file:///path/to/output.pptx)`

   Clicking the link opens the local file in your OS. The raw path is also shown for reference.

## Key Files & Directories

- `src/app/*` – Next.js routes and pages
- `src/components/chat/*` – Chat UI components
- `src-tauri/src/lib.rs` – Tauri commands, agent orchestration, thumbnails, DB access
- `src-tauri/src/db.rs` – SQLite schema and queries
- `src-tauri/src/grpc_client.rs` – gRPC client calls to agents
- `backend/mcp/*.py` – Python agent servers
- `proto/audio_service.proto` – Protobuf definitions for services

## Limitation

- Initial chat responses are hardcoded to provide immediate feedback while Python agents load their models into memory to ensure a responsive user experience during the 10–30 second startup period.
- Model inference runs locally and may be slower on CPU-only systems. OpenVINO optimization is used where available to improve performance.
- - **Model Limitations**: The project uses pre-trained models that are not fine-tuned on MP4-specific content:
  - **Transcription**: OpenAI Whisper `base` model for speech-to-text.
  - **Vision**: DETR (object detection), BLIP (captioning), and TrOCR (OCR) for visual analysis.
  - **Generation**: FLAN-T5-small for text summarization.

  - If time permits, these models can be fine-tuned on domain-specific MP4 video content to improve accuracy and contextual understanding for video-based queries.

## Troubleshooting

- Ensure `ffmpeg` is installed and accessible on PATH if thumbnails fail.
- If agents don’t start, verify Python env and the packages in `backend/requirements.txt` are installed; check console logs for `[agent stdout]`/`[agent stderr]`.
- Port conflicts (50051–50053) will prevent connections; free or change ports as needed.

## License

Proprietary. All rights reserved.

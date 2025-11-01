<p align="center">
  <img src="public/trace.svg" alt="Auralink" width="250" height=auto />
</p>

<div align="center">
  <a href="https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54"><img alt="Python" src="https://img.shields.io/badge/python-3670A0?style=flat&logo=python&logoColor=ffdd54" /></a>
  <a href="https://img.shields.io/badge/Rust-000000?logo=rust&logoColor=white"><img alt="Rust" src="https://shields.io/badge/-Rust-3776AB?style=flat&logo=rust" /></a>
  <a href="https://github.com/aqilmarwan/auralink/graphs/contributors"><img alt="Contributors" src="https://img.shields.io/github/contributors/aqilmarwan/auralink?color=blue" /></a>
  <a href="https://github.com/aqilmarwan/auralink/commits"><img alt="Last Commit" src="https://img.shields.io/github/last-commit/aqilmarwan/auralink?color=brightgreen" /></a>
  <a href="https://github.com/aqilmarwan/auralink/issues"><img alt="Open Issues" src="https://img.shields.io/github/issues/aqilmarwan/auralink?color=brightgreen&label=issues" /></a>
  <img alt="License" src="https://img.shields.io/badge/license-Proprietary-lightgrey" />
  <a href="https://github.com/aqilmarwan/auralink/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/aqilmarwan/auralink?style=flat&color=blue" /></a>
  <a href="https://github.com/aqilmarwan/auralink/network/members"><img alt="Forks" src="https://img.shields.io/github/forks/aqilmarwan/auralink?style=flat&color=blue" /></a>

  <a> Modern, local-first AI assistant for video understanding and document generation. Auralink pairs a sleek Next.js UI with a Rust (Tauri) app and Python micro-agents over gRPC for transcription, vision analysis, and content generation (PDF/PPT). <a>
</div>

> [!NOTE]
> Development has stopped indefinitely!

> [!WARNING]
> Auralink is currently in the early stages of development and is not yet ready for daily use!

<p align="center">
  <img src="public/ss.png" alt="Auralink UI" width="1020" />
</p>

## Features

- **Chat-first workflow**: Ask questions about a video or request outcomes (e.g., “Create a PowerPoint”).
- **Local agents**:
  - Transcription (audio → text)
  - Vision (objects, graphs/plots, caption)
  - Generation (summary, PDF, PowerPoint)
- **Fast UI**: Smooth, bottom-up chronological chat with optimistic updates and typing animation.
- **Thumbnails**: Auto-generated via ffmpeg for quick visual context.
- **Local persistence**: SQLite (via rusqlite) stores files and chat history.

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

### Data flow (chat)

1. User submits a prompt in `ChatInput.tsx`.
2. Frontend invokes `send_message` (Tauri) → `src-tauri/src/lib.rs`.
3. Rust persists the user message, scores intent, and calls agents via gRPC as needed.
4. Agent responses are post-processed into friendly text and saved as assistant messages.
5. Frontend invalidates the messages query; UI displays messages in chronological order (newest at bottom). Assistant responses appear immediately after the user’s prompt.

### Persistence

- SQLite DB file in the OS’s local data dir: `auralink/auralink.sqlite`.
- Tables: `files`, `messages`.
- Message listing is ordered by `created_at` ascending and paginated using `createdAt` cursors for stable chronological scroll.

### Media handling

- Videos are saved to the same data directory.
- Thumbnails are created via `ffmpeg` at 1s mark and stored under a `thumbs/` directory.

### Agents and ports

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
- Assistant responses must appear immediately after the corresponding user prompt in the chat and render cleanly.
- When generating a file (PDF/PPT), the assistant message includes a clickable `file://` hyperlink with the full local path for quick access.

## Tech Stack

- UI: Next.js 14, React 18, Tailwind, React Query, Mantine hooks, React Markdown
- Desktop: Tauri 2 (Rust), rusqlite, tonic (gRPC client)
- Agents: Python 3, gRPC, Whisper, OpenVINO/ONNX Runtime, MoviePy, NumPy
- Media tooling: ffmpeg (required on host)

## Getting Started

### Prerequisites

- Node.js 18+ and pnpm/npm
- Rust toolchain and Tauri prerequisites (see Tauri docs for your OS)
- Python 3.11+
- ffmpeg installed and on PATH

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

1. Open the app and upload/register a video.
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

## Design Notes

- Responses are composed into concise, user-friendly sentences while retaining essential details.
- Errors from gRPC are sanitized into helpful messages; transient transport failures are retried lightly.
- Pagination is stable via `createdAt` cursors, so infinite scroll behaves predictably.

## Troubleshooting

- Ensure `ffmpeg` is installed and accessible on PATH if thumbnails fail.
- If agents don’t start, verify Python env and the packages in `backend/requirements.txt` are installed; check console logs for `[agent stdout]`/`[agent stderr]`.
- Port conflicts (50051–50053) will prevent connections; free or change ports as needed.

## License

Proprietary. All rights reserved.

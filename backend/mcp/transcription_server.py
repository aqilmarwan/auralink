"""
Transcription MCP Server
Handles speech-to-text extraction using local Whisper models (OpenVINO optimized)
Exposes gRPC service for TranscriptionService
"""
import asyncio
import whisper
from typing import Dict, Any, Optional
from pathlib import Path
import uuid
from datetime import datetime
import grpc
from concurrent import futures
import sys
import os

# Ensure generated stubs are on PYTHONPATH and generate if missing
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
GEN_DIR = os.path.join(PROJECT_ROOT, 'backend', 'generated')
if GEN_DIR not in sys.path:
    sys.path.insert(0, GEN_DIR)

try:
    from openvino.runtime import Core
    _OPENVINO_AVAILABLE = True
except Exception:
    Core = None  # type: ignore
    _OPENVINO_AVAILABLE = False
import numpy as np

def ensure_stubs():
    try:
        # Prefer modules generated from audio_service.proto
        import audio_service_pb2 as auralink_pb2  # type: ignore
        import audio_service_pb2_grpc as auralink_pb2_grpc  # type: ignore
        sys.modules['auralink_pb2'] = auralink_pb2
        sys.modules['auralink_pb2_grpc'] = auralink_pb2_grpc
        return True
    except Exception:
        pass
    # Attempt to generate stubs
    try:
        os.makedirs(GEN_DIR, exist_ok=True)
        from grpc_tools import protoc  # type: ignore
        proto_path = os.path.join(PROJECT_ROOT, 'proto', 'audio_service.proto')
        protoc.main([
            'protoc',
            f'-I{os.path.join(PROJECT_ROOT, "proto")}',
            f'--python_out={GEN_DIR}',
            f'--grpc_python_out={GEN_DIR}',
            proto_path,
        ])
        return True
    except Exception as e:
        print(f"[Transcription Agent] Failed to generate stubs: {e}")
        return False

_GRPC_AVAILABLE = ensure_stubs()
try:
    import audio_service_pb2 as auralink_pb2  # type: ignore
    import audio_service_pb2_grpc as auralink_pb2_grpc  # type: ignore
except Exception:
    # Still not available
    auralink_pb2 = None  # type: ignore
    auralink_pb2_grpc = None  # type: ignore
    _GRPC_AVAILABLE = False
if not _GRPC_AVAILABLE:
    print("[Transcription Agent] Warning: gRPC proto files not found.")


if auralink_pb2_grpc is not None:
    BaseServicer = auralink_pb2_grpc.TranscriptionServiceServicer  # type: ignore
else:
    class BaseServicer(object):
        pass

class TranscriptionService(BaseServicer):
    """gRPC service implementation for Transcription"""
    
    def __init__(self, model_path: str = "base", device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        self.whisper_model: Optional[Any] = None
        self.core = Core() if _OPENVINO_AVAILABLE else None
        print(f"[Transcription Agent] Initializing with model: {model_path}, device: {device}")
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model (OpenVINO optimized preferred, fallback to Hugging Face) - runs on startup"""
        try:
            print(f"[Transcription Agent] Loading Whisper model: {self.model_path}...")
            # In some dev environments, system root CAs cause SSL verify failures.
            # Fall back to an unverified HTTPS context to allow model download.
            try:
                import ssl  # type: ignore
                ssl._create_default_https_context = ssl._create_unverified_context  # type: ignore
                os.environ.setdefault("PYTHONHTTPSVERIFY", "0")
                print("[Transcription Agent] HTTPS cert verification disabled for model download (dev only)")
            except Exception:
                pass
            # Try to load OpenVINO optimized model first
            # model_xml = Path(f"models/whisper_{self.model_path}.xml")
            # if model_xml.exists():
            #     model = self.core.read_model(str(model_xml))
            #     self.whisper_model = self.core.compile_model(model, self.device)
            #     print(f"[Transcription Agent] Loaded OpenVINO optimized Whisper model: {self.model_path}")
            # else:
            #     # Fallback to standard Whisper
            self.whisper_model = whisper.load_model(self.model_path)
            print(f"[Transcription Agent] Whisper model '{self.model_path}' loaded successfully and ready!")
        except Exception as e:
            print(f"[Transcription Agent] Error loading model: {e}")
            raise
    
    def TranscribeVideo(self, request, context):
        """gRPC handler for TranscribeVideo"""
        try:
            file_id = request.file_id
            audio_data = request.audio_data
            format_type = request.format or "mp4"
            
            # Write temp file
            import tempfile
            temp_path = None
            try:
                if audio_data:
                    temp_fd, temp_path = tempfile.mkstemp(suffix=f".{format_type}")
                    with os.fdopen(temp_fd, 'wb') as f:
                        f.write(audio_data)
                
                # Extract audio if video (use ffmpeg to avoid moviepy dependency)
                if format_type in ["mp4", "avi", "mov", "mkv"]:
                    audio_temp = tempfile.mkstemp(suffix=".wav")[1]
                    import subprocess
                    cmd = [
                        "ffmpeg", "-y", "-i", temp_path,
                        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                        audio_temp
                    ]
                    try:
                        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        audio_file = audio_temp
                        cleanup_audio = True
                    except Exception as e:
                        raise RuntimeError(f"ffmpeg audio extraction failed: {e}")
                else:
                    audio_file = temp_path
                    cleanup_audio = False
                
                # Run transcription (blocking in thread pool for async)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    loop.run_in_executor(
                        None,
                        lambda: self.whisper_model.transcribe(audio_file)
                    )
                )
                loop.close()
                
                # Build response
                segments = [
                    auralink_pb2.TimestampSegment(
                        text=seg.get("text", ""),
                        start_time=seg.get("start", 0.0),
                        end_time=seg.get("end", 0.0)
                    )
                    for seg in result.get("segments", [])
                ]
                
                response = auralink_pb2.TranscribeResponse(
                    text=result.get("text", ""),
                    segments=segments,
                    language=result.get("language", "unknown"),
                    confidence=0.95
                )
                
                # Cleanup
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                if cleanup_audio and os.path.exists(audio_file):
                    os.unlink(audio_file)
                
                return response
                
            except Exception as e:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(str(e))
                return auralink_pb2.TranscribeResponse(text="", language="unknown", confidence=0.0)
                
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return auralink_pb2.TranscribeResponse(text="", language="unknown", confidence=0.0)


def serve(port: int = 50051, model_path: str = "base"):
    """Start gRPC server"""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        options=[
            ('grpc.max_send_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),
        ],
    )
    if not _GRPC_AVAILABLE or auralink_pb2_grpc is None:
        print("[Transcription Agent] Stubs unavailable; exiting.")
        return
    # Add service - models load here on instantiation
    service = TranscriptionService(model_path=model_path)
    auralink_pb2_grpc.add_TranscriptionServiceServicer_to_server(service, server)  # type: ignore
    
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"[Transcription Agent] gRPC server started on port {port}")
    print(f"[Transcription Agent] Model '{model_path}' ready for requests")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("[Transcription Agent] Shutting down...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=50051)
    parser.add_argument('--model', type=str, default='base')
    args = parser.parse_args()
    
    serve(port=args.port, model_path=args.model)

"""
Generation MCP Server
Handles PDF/PPT generation and summarization using local models
Exposes gRPC service for GenerationService
"""
import asyncio
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

try:
    from transformers import AutoTokenizer, T5ForConditionalGeneration
    import torch
    _TRANSFORMERS_AVAILABLE = True
except Exception:
    _TRANSFORMERS_AVAILABLE = False

def ensure_stubs():
    try:
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
        print(f"[Generation Agent] Failed to generate stubs: {e}")
        return False

_GRPC_AVAILABLE = ensure_stubs()
try:
    import audio_service_pb2 as auralink_pb2  # type: ignore
    import audio_service_pb2_grpc as auralink_pb2_grpc  # type: ignore
except Exception:
    auralink_pb2 = None  # type: ignore
    auralink_pb2_grpc = None  # type: ignore
    _GRPC_AVAILABLE = False
if not _GRPC_AVAILABLE:
    print("[Generation Agent] Warning: gRPC proto files not found.")


if auralink_pb2_grpc is not None:
    BaseServicer = auralink_pb2_grpc.GenerationServiceServicer  # type: ignore
else:
    class BaseServicer(object):
        pass

class GenerationService(BaseServicer):
    """gRPC service implementation for Generation"""
    
    def __init__(self, device: str = "cpu"):
        self.device = device
        self.core = Core() if _OPENVINO_AVAILABLE else None
        
        # Initialize model placeholders
        self.summarization_model = None
        self.summarization_tokenizer = None
        self._models_loaded = False
        
        print(f"[Generation Agent] Initializing with device: {device}")
        # Load models immediately on startup
        self._load_models()
    
    def _load_models(self):
        """Load generation models (summarization) - runs on startup"""
        if self._models_loaded:
            return
        
        try:
            print("[Generation Agent] Starting model initialization...")
            
            if not _TRANSFORMERS_AVAILABLE:
                print("[Generation Agent] Warning: transformers not available, summarization will use basic methods")
                self._models_loaded = True
                return
            
            # Summarization Model - T5 or FLAN-T5 (small for faster inference)
            print("[Generation Agent] Loading summarization model (FLAN-T5-small)...")
            model_name = "google/flan-t5-small"  # Lightweight, good for summaries
            self.summarization_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.summarization_model = T5ForConditionalGeneration.from_pretrained(model_name)
            
            if hasattr(self.summarization_model, 'to'):
                self.summarization_model = self.summarization_model.to(self.device)
            
            self._models_loaded = True
            print("[Generation Agent] Summarization model loaded successfully and ready!")
            
        except Exception as e:
            print(f"[Generation Agent] Error loading models: {e}")
            print("[Generation Agent] Continuing without models - will use basic summarization")
            self._models_loaded = True  # Allow server to start even if excell fail
    
    def GenerateSummary(self, request, context):
        """gRPC handler for GenerateSummary"""
        try:
            file_id = request.file_id
            # TODO: Fetch chat history from DB using file_id
            # For now, use placeholder
            chat_text = ""  # Would fetch from DB
            
            if self.summarization_model and self.summarization_tokenizer and chat_text:
                prompt = f"Summarize the following conversation in 2-3 sentences:\n\n{chat_text[:1000]}"
                inputs = self.summarization_tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.summarization_model.generate(
                        **inputs,
                        max_length=150,
                        num_beams=4,
                        early_stopping=True
                    )
                
                summary = self.summarization_tokenizer.decode(outputs[0], skip_special_tokens=True)
                key_topics = []
            else:
                summary = "Summary not available (no chat history or model)"
                key_topics = []
            
            return auralink_pb2.SummaryResponse(
                summary=summary,
                key_topics=key_topics
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return auralink_pb2.SummaryResponse(summary="", key_topics=[])
    
    def GeneratePDF(self, request, context):
        """gRPC handler for GeneratePDF"""
        try:
            file_id = request.file_id
            # TODO: Implement actual PDF generation
            output_path = f"/tmp/{file_id}_summary.pdf"
            
            return auralink_pb2.GenerateResponse(
                output_file_path=output_path,
                success=True,
                error_message=""
            )
        except Exception as e:
            return auralink_pb2.GenerateResponse(
                output_file_path="",
                success=False,
                error_message=str(e)
            )
    
    def GeneratePowerPoint(self, request, context):
        """gRPC handler for GeneratePowerPoint"""
        try:
            file_id = request.file_id
            # TODO: Implement actual PPT generation
            output_path = f"/tmp/{file_id}_presentation.pptx"
            
            return auralink_pb2.GenerateResponse(
                output_file_path=output_path,
                success=True,
                error_message=""
            )
        except Exception as e:
            return auralink_pb2.GenerateResponse(
                output_file_path="",
                success=False,
                error_message=str(e)
            )


def serve(port: int = 50051):
    """Start gRPC server"""
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4),
        options=[
            ('grpc.max_send_message_length', 50 * 1024 * 1024),
            ('grpc.max_receive_message_length', 50 * 1024 * 1024),
        ],
    )
    if not _GRPC_AVAILABLE or auralink_pb2_grpc is None:
        print("[Generation Agent] Stubs unavailable; exiting.")
        return
    # Add service - models load here on instantiation
    service = GenerationService()
    auralink_pb2_grpc.add_GenerationServiceServicer_to_server(service, server)  # type: ignore
    
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"[Generation Agent] gRPC server started on port {port}")
    print(f"[Generation Agent] Models ready for requests")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("[Generation Agent] Shutting down...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=50053)
    args = parser.parse_args()
    
    serve(port=args.port)

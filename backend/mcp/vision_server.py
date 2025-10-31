"""
Vision MCP Server
Handles object recognition, captioning, and text/graph extraction using local models
Exposes gRPC service for VisionService
"""
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import cv2
import numpy as np
import io
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
from PIL import Image
import torch
from transformers import (
    BlipProcessor, BlipForConditionalGeneration,
    TrOCRProcessor, VisionEncoderDecoderModel,
    AutoImageProcessor, AutoModelForObjectDetection
)

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
        print(f"[Vision Agent] Failed to generate stubs: {e}")
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
    print("[Vision Agent] Warning: gRPC proto files not found.")


if auralink_pb2_grpc is not None:
    BaseServicer = auralink_pb2_grpc.VisionServiceServicer  # type: ignore
else:
    class BaseServicer(object):
        pass

class VisionService(BaseServicer):
    """gRPC service implementation for Vision"""
    
    def __init__(self, device: str = "cpu"):
        self.device = device
        self.core = Core() if _OPENVINO_AVAILABLE else None
        
        # Initialize model placeholders
        self.object_detection_model = None
        self.captioning_model = None
        self.captioning_processor = None
        self.ocr_model = None
        self.ocr_processor = None
        self.od_processor = None
        
        self._models_loaded = False
        
        print(f"[Vision Agent] Initializing with device: {device}")
        # Load models immediately on startup
        self._load_models()
    
    def _load_models(self):
        """Load vision models (OpenVINO optimized preferred) - runs on startup"""
        if self._models_loaded:
            return
        
        try:
            print("[Vision Agent] Starting model initialization...")
            
            # Object Detection - using DETR (can be replaced with OpenVINO YOLOv8)
            print("[Vision Agent] Loading object detection model (DETR)...")
            self.od_processor = AutoImageProcessor.from_pretrained(
                "facebook/detr-resnet-50"
            )
            self.object_detection_model = AutoModelForObjectDetection.from_pretrained(
                "facebook/detr-resnet-50"
            ).to(self.device)
            
            # Captioning Model - BLIP
            print("[Vision Agent] Loading BLIP captioning model...")
            self.captioning_processor = BlipProcessor.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
            self.captioning_model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            ).to(self.device)
            
            # OCR Model - TrOCR
            print("[Vision Agent] Loading TrOCR OCR model...")
            self.ocr_processor = TrOCRProcessor.from_pretrained(
                "microsoft/trocr-base-printed"
            )
            self.ocr_model = VisionEncoderDecoderModel.from_pretrained(
                "microsoft/trocr-base-printed"
            ).to(self.device)
            
            self._models_loaded = True
            print("[Vision Agent] All models loaded successfully and ready!")
            
        except Exception as e:
            print(f"[Vision Agent] Error loading models: {e}")
            raise
    
    def _load_image(self, image_data: bytes) -> Image.Image:
        """Load image from bytes"""
        return Image.open(io.BytesIO(image_data)).convert("RGB")
    
    def DetectObjects(self, request, context):
        """gRPC handler for DetectObjects"""
        try:
            image_data = request.image_data
            image = self._load_image(image_data)
            
            # Object detection
            inputs = self.od_processor(images=image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                outputs = self.object_detection_model(**inputs)
            
            results = self.od_processor.post_process_object_detection(
                outputs, threshold=0.5
            )[0]
            
            objects = []
            for score, label, box in zip(
                results["scores"], results["labels"], results["boxes"]
            ):
                objects.append(
                    auralink_pb2.DetectedObject(
                        label=self.object_detection_model.config.id2label[label.item()],
                        confidence=float(score.item()),
                        bbox=auralink_pb2.BoundingBox(
                            x=int(box[0].item()),
                            y=int(box[1].item()),
                            width=int((box[2] - box[0]).item()),
                            height=int((box[3] - box[1]).item())
                        )
                    )
                )
            
            # Generate caption
            caption_inputs = self.captioning_processor(image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                caption_out = self.captioning_model.generate(**caption_inputs, max_length=50)
            caption = self.captioning_processor.decode(caption_out[0], skip_special_tokens=True)
            
            return auralink_pb2.ObjectDetectionResponse(
                objects=objects,
                caption=caption
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return auralink_pb2.ObjectDetectionResponse(caption="")
    
    def ExtractText(self, request, context):
        """gRPC handler for ExtractText"""
        try:
            image_data = request.image_data
            image = self._load_image(image_data)
            
            pixel_values = self.ocr_processor(image, return_tensors="pt").pixel_values.to(self.device)
            with torch.no_grad():
                generated_ids = self.ocr_model.generate(pixel_values)
                generated_text = self.ocr_processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0]
            
            text_region = auralink_pb2.ExtractedText(
                text=generated_text,
                bbox=auralink_pb2.BoundingBox(x=0, y=0, width=image.width, height=image.height),
                confidence=0.9
            )
            
            return auralink_pb2.TextExtractionResponse(
                text_regions=[text_region],
                full_text=generated_text
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return auralink_pb2.TextExtractionResponse(full_text="")
    
    def IdentifyGraphs(self, request, context):
        """gRPC handler for IdentifyGraphs"""
        try:
            image_data = request.image_data
            image = self._load_image(image_data)
            
            # Use object detection + captioning to identify graphs
            det_response = self.DetectObjects(request, context)
            caption = det_response.caption
            
            # Simple heuristic for graph detection
            graph_keywords = ["chart", "graph", "diagram", "plot", "bar", "line", "pie"]
            graphs = []
            if any(keyword in caption.lower() for keyword in graph_keywords):
                graph_type = "unknown"
                if "bar" in caption.lower():
                    graph_type = "bar"
                elif "line" in caption.lower() or "plot" in caption.lower():
                    graph_type = "line"
                elif "pie" in caption.lower():
                    graph_type = "pie"
                
                graphs.append(
                    auralink_pb2.GraphInfo(
                        type=graph_type,
                        data_summary=caption,
                        bbox=auralink_pb2.BoundingBox(x=0, y=0, width=image.width, height=image.height)
                    )
                )
            
            return auralink_pb2.GraphIdentificationResponse(
                graphs=graphs,
                description=caption
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return auralink_pb2.GraphIdentificationResponse(description="")


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
        print("[Vision Agent] Stubs unavailable; exiting.")
        return
    # Add service - models load here on instantiation
    service = VisionService()
    auralink_pb2_grpc.add_VisionServiceServicer_to_server(service, server)  # type: ignore
    
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"[Vision Agent] gRPC server started on port {port}")
    print(f"[Vision Agent] Models ready for requests")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("[Vision Agent] Shutting down...")
        server.stop(0)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=50052)
    args = parser.parse_args()
    
    serve(port=args.port)

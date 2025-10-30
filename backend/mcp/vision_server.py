"""
Vision MCP Server
Handles object recognition, captioning, and text/graph extraction using local models
"""
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import torch
from transformers import (
    BlipProcessor, BlipForConditionalGeneration,
    TrOCRProcessor, VisionEncoderDecoderModel,
    AutoImageProcessor, AutoModelForObjectDetection
)
from openvino.runtime import Core

from .protocol import MCPEndpoint, AgentType, MCPMessage, MCPMessageType


class VisionMCPServer(MCPEndpoint):
    """MCP Server for Vision Agent"""
    
    def __init__(self, device: str = "cpu"):
        super().__init__(AgentType.VISION)
        self.device = device
        self.core = Core()
        
        # Initialize models (lazy loading)
        self.object_detection_model = None
        self.captioning_model = None
        self.captioning_processor = None
        self.ocr_model = None
        self.ocr_processor = None
        self.graph_detection_model = None
        
        self._models_loaded = False
    
    def _load_models(self):
        """Load vision models (OpenVINO optimized preferred)"""
        if self._models_loaded:
            return
        
        try:
            # Object Detection - try OpenVINO first
            # For local inference, use Hugging Face transformers
            # YOLOv8 or DETR models work well here
            
            # Captioning Model - BLIP
            print("Loading BLIP captioning model...")
            self.captioning_processor = BlipProcessor.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            )
            self.captioning_model = BlipForConditionalGeneration.from_pretrained(
                "Salesforce/blip-image-captioning-base"
            ).to(self.device)
            
            # OCR Model - TrOCR
            print("Loading TrOCR OCR model...")
            self.ocr_processor = TrOCRProcessor.from_pretrained(
                "microsoft/trocr-base-printed"
            )
            self.ocr_model = VisionEncoderDecoderModel.from_pretrained(
                "microsoft/trocr-base-printed"
            ).to(self.device)
            
            # Object Detection - using YOLOv8 via transformers or OpenVINO
            print("Loading object detection model...")
            # For simplicity, using transformers DETR
            # In production, use OpenVINO optimized YOLOv8
            self.od_processor = AutoImageProcessor.from_pretrained(
                "facebook/detr-resnet-50"
            )
            self.object_detection_model = AutoModelForObjectDetection.from_pretrained(
                "facebook/detr-resnet-50"
            ).to(self.device)
            
            self._models_loaded = True
            print("All vision models loaded successfully")
            
        except Exception as e:
            print(f"Error loading vision models: {e}")
            raise
    
    async def handle_message(self, message: MCPMessage) -> MCPMessage:
        """Handle incoming MCP messages"""
        if not self._models_loaded:
            self._load_models()
        
        if message.message_type == MCPMessageType.REQUEST:
            return await self._handle_request(message)
        return message
    
    async def _handle_request(self, message: MCPMessage) -> MCPMessage:
        """Handle request messages"""
        method = message.method
        
        handlers = {
            "detect_objects": self._detect_objects,
            "extract_text": self._extract_text,
            "caption_image": self._caption_image,
            "identify_graphs": self._identify_graphs,
            "process_frame": self._process_frame
        }
        
        if method in handlers:
            result = await handlers[method](
                image_data=message.params.get("image_data"),
                image_path=message.params.get("image_path"),
                frame_number=message.params.get("frame_number")
            )
            
            response = MCPMessage(
                message_id=str(uuid.uuid4()),
                timestamp=datetime.utcnow().isoformat(),
                source=self.agent_type,
                target=message.source,
                message_type=MCPMessageType.RESPONSE,
                method=method,
                params={},
                result=result
            )
            return response
        
        # Unknown method
        error_response = MCPMessage(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            source=self.agent_type,
            target=message.source,
            message_type=MCPMessageType.ERROR,
            method=method,
            params={},
            error={"code": -32601, "message": f"Method not found: {method}"}
        )
        return error_response
    
    def _load_image(self, image_data: Optional[bytes] = None, image_path: Optional[str] = None) -> Image.Image:
        """Load image from bytes or path"""
        if image_data:
            return Image.open(io.BytesIO(image_data)).convert("RGB")
        elif image_path:
            return Image.open(image_path).convert("RGB")
        else:
            raise ValueError("Either image_data or image_path must be provided")
    
    async def _detect_objects(
        self,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Detect objects in image"""
        import io
        loop = asyncio.get_event_loop()
        
        def _detect():
            image = self._load_image(image_data, image_path)
            inputs = self.od_processor(images=image, return_tensors=" Tir").to(self.device)
            
            with torch.no_grad():
                outputs = self.object_detection_model(**inputs)
            
            # Process outputs
            results = self.od_processor.post_process_object_detection(
                outputs, threshold=0.5
            )[0]
            
            objects = []
            for score, label, box in zip(
                results["scores"], results["labels"], results["boxes"]
            ):
                objects.append({
                    "label": self.object_detection_model.config.id2label[label.item()],
                    "confidence": float(score.item()),
                    "bbox": {
                        "x": int(box[0].item()),
                        "y": int(box[1].item()),
                        "width": int((box[2] - box[0]).item()),
                        "height": int((box[3] - box[1]).item())
                    }
                })
            
            return {"objects": objects}
        
        result = await loop.run_in_executor(None, _detect)
        
        # Generate caption
        caption_result = await self._caption_image(image_data, image_path)
        result["caption"] = caption_result.get("caption", "")
        
        return result
    
    async def _caption_image(
        self,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate caption for image"""
        import io
        loop = asyncio.get_event_loop()
        
        def _caption():
            image = self._load_image(image_data, image_path)
            inputs = self.captioning_processor(image, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                out = self.captioning_model.generate(**inputs, max_length=50)
            
            caption = self.captioning_processor.decode(out[0], skip_special_tokens=True)
            return {"caption": caption}
        
        return await loop.run_in_executor(None, _caption)
    
    async def _extract_text(
        self,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Extract text from image using OCR"""
        import io
        loop = asyncio.get_event_loop()
        
        def _extract():
            image = self._load_image(image_data, image_path)
            pixel_values = self.ocr_processor(image, return_tensors="pt").pixel_values.to(self.device)
            
            with torch.no_grad():
                generated_ids = self.ocr_model.generate(pixel_values)
                generated_text = self.ocr_processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0]
            
            # For more detailed text extraction with bounding boxes,
            # you would use a layout analysis model like PaddleOCR or EasyOCR
            return {
                "full_text": generated_text,
                "text_regions": [{
                    "text": generated_text,
                    "bbox": {"x": 0, "y": 0, "width": image.width, "height": image.height},
                    "confidence": 0.9
                }]
            }
        
        return await loop.run_in_executor(None, _extract)
    
    async def _identify_graphs(
        self,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Identify and describe graphs/charts in image"""
        import io
        
        # First detect objects to find potential graphs
        detection_result = await self._detect_objects(image_data, image_path)
        
        # Filter for graph-like objects (this is a simplified approach)
        # TO DO - Use a specialized graph detection model in prod
        graph_keywords = ["chart", "graph", "diagram", "plot", "bar", "line", "pie"]
        potential_graphs = [
            obj for obj in detection_result.get("objects", [])
            if any(keyword in obj["label"].lower() for keyword in graph_keywords)
        ]
        
        # Generate description
        caption_result = await self._caption_image(image_data, image_path)
        description = caption_result.get("caption", "")
        
        graphs = []
        if potential_graphs or any(keyword in description.lower() for keyword in graph_keywords):
            # Classify graph type using caption or additional model
            graph_type = "unknown"
            if "bar" in description.lower():
                graph_type = "bar"
            elif "line" in description.lower() or "plot" in description.lower():
                graph_type = "line"
            elif "pie" in description.lower():
                graph_type = "pie"
            
            graphs.append({
                "type": graph_type,
                "data_summary": description,
                "bbox": {
                    "x": 0, "y": 0,
                    "width": 0, "height": 0 
                }
            })
        
        return {
            "graphs": graphs,
            "description": description
        }
    
    async def _process_frame(
        self,
        image_data: Optional[bytes] = None,
        image_path: Optional[str] = None,
        frame_number: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Process a video frame comprehensively"""
        objects = await self._detect_objects(image_data, image_path)
        text = await self._extract_text(image_data, image_path)
        graphs = await self._identify_graphs(image_data, image_path)
        
        return {
            "frame_number": frame_number,
            "objects": objects.get("objects", []),
            "text": text.get("full_text", ""),
            "text_regions": text.get("text_regions", []),
            "graphs": graphs.get("graphs", []),
            "caption": objects.get("caption", "")
        }
    
    async def run(self):
        """Run the MCP server message loop"""
        while True:
            try:
                message = await self.message_queue.get()
                if message.target == self.agent_type or message.target is None:
                    response = await self.handle_message(message)
                    if response.message_type == MCPMessageType.RESPONSE:
                        # Send response back to source
                        await self.message_queue.put(response)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in Vision MCP server: {e}")
                await asyncio.sleep(1)
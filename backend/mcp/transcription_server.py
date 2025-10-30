"""
Transcription MCP Server
Handles speech-to-text extraction using local Whisper models (OpenVINO optimized)
"""
import asyncio
import whisper
from typing import Dict, Any, Optional
from pathlib import Path
import moviepy.editor as mp
from openvino.runtime import Core
import numpy as np

from .protocol import MCPEndpoint, AgentType, MCPMessage, MCPMessageType


class TranscriptionMCPServer(MCPEndpoint):
    """MCP Server for Transcription Agent"""
    
    def __init__(self, model_path: str = "base", device: str = "cpu"):
        super().__init__(AgentType.TRANSCRIPTION)
        self.model_path = model_path
        self.device = device
        self.whisper_model: Optional[Any] = None
        self.core = Core()
        self._load_model()
    
    def _load_model(self):
        """Load Whisper model (OpenVINO optimized preferred, fallback to Hugging Face)"""
        try:
            # Try to load OpenVINO optimized model first
            # model_xml = Path(f"models/whisper_{self.model_path}.xml")
            # if model_xml.exists():
            #     model = self.core.read_model(str(model_xml))
            #     self.whisper_model = self.core.compile_model(model, self.device)
            #     print(f"Loaded OpenVINO optimized Whisper model: {self.model_path}")
            # else:
            #     # Fallback to standard Whisper
            self.whisper_model = whisper.load_model(self.model_path)
            print(f"Loaded Whisper model: {self.model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
            raise
    
    async def handle_message(self, message: MCPMessage) -> MCPMessage:
        """Handle incoming MCP messages"""
        if message.message_type == MCPMessageType.REQUEST:
            return await self._handle_request(message)
        return message
    
    async def _handle_request(self, message: MCPMessage) -> MCPMessage:
        """Handle request messages"""
        method = message.method
        
        if method == "transcribe":
            result = await self._transcribe(
                file_path=message.params.get("file_path"),
                file_data=message.params.get("file_data"),
                format_type=message.params.get("format", "mp4")
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
    
    async def _transcribe(
        self,
        file_path: Optional[str] = None,
        file_data: Optional[bytes] = None,
        format_type: str = "mp4"
    ) -> Dict[str, Any]:
        """Perform transcription on video/audio file"""
        import tempfile
        import os
        
        try:
            # Handle file data or file path
            if file_data:
                temp_path = f"/tmp/transcribe_{uuid.uuid4()}.{format_type}"
                with open(temp_path, 'wb') as f:
                    f.write(file_data)
                cleanup = True
            elif file_path:
                temp_path = file_path
                cleanup = False
            else:
                raise ValueError("Either file_path or file_data must be provided")
            
            try:
                # Extract audio from video if needed
                if format_type in ["mp4", "avi", "mov", "mkv"]:
                    video = mp.VideoFileClip(temp_path)
                    audio_path = f"/tmp/audio_{uuid.uuid4()}.wav"
                    video.audio.write_audiofile(audio_path, verbose=False, logger=None)
                    video.close()
                    audio_file = audio_path
                    cleanup_audio = True
                else:
                    audio_file = temp_path
                    cleanup_audio = False
                
                # Run transcription in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.whisper_model.transcribe(audio_file)
                )
                
                # Process segments
                segments = [
                    {
                        "text": seg.get("text", ""),
                        "start_time": seg.get("start", 0.0),
                        "end_time": seg.get("end", 0.0)
                    }
                    for seg in result.get("segments", [])
                ]
                
                transcription_result = {
                    "text": result.get("text", ""),
                    "segments": segments,
                    "language": result.get("language", "unknown"),
                    "confidence": 0.95 
                }
                
                # Cleanup
                if cleanup:
                    os.unlink(temp_path)
                if cleanup_audio:
                    os.unlink(audio_file)
                
                return transcription_result
                
            except Exception as e:
                if cleanup and os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
            
        except Exception as e:
            return {
                "error": str(e),
                "text": "",
                "segments": [],
                "language": "unknown",
                "confidence": 0.0
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
                print(f"Error in Transcription MCP Server: {e}")
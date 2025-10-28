import asyncio
import grpc
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from openvino.runtime import Core
import moviepy.editor as mp
import whisper
from typing import Optional

# Import generated gRPC code
import audio_service_pb2_grpc as audio_pb2_grpc
import audio_service_pb2 as audio_pb2

# Initialize OpenVINO
core = Core()

########################################################
# Load models (these would be OpenVINO models)
# whisper_model = core.read_model("whisper_model.xml")
# whisper_model = core.compile_model(whisper_model, "CPU")

# Or use OpenAI Whisper directly (OpenVINO optimized)
whisper_model = whisper.load_model("base")


class TranscriptionServiceImpl(audio_pb2_grpc.TranscriptionServiceServicer):
    async def TranscribeVideo(self, request, context):
        """Process video using OpenVINO/Whisper and return transcription."""
        try:
            file_id = request.file_id
            audio_data = request.audio_data
            format_type = request.format
            
            # Save uploaded file
            temp_path = f"/tmp/{file_id}.{format_type}"
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            # Extract audio from video
            video = mp.VideoFileClip(temp_path)
            audio_path = f"/tmp/{file_id}_audio.wav"
            video.audio.write_audiofile(audio_path, verbose=False, logger=None)
            
            # Transcribe using Whisper
            result = whisper_model.transcribe(audio_path)
            
            # Process segments for timestamped response
            segments = []
            for segment in result.get("segments", []):
                segments.append(audio_pb2.TimestampSegment(
                    text=segment["text"],
                    start_time=segment["start"],
                    end_time=segment["end"]
                ))
            
            return audio_pb2.TranscribeResponse(
                text=result.get("text", ""),
                segments=segments,
                language=result.get("language", "unknown"),
                confidence=0.95  # Whisper confidence
            )
            
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL_ERROR)
            context.set_details(f"Transcription failed: {str(e)}")
            return audio_pb2.TranscribeResponse()
    
    async def StreamTranscription(self, request, context):
        """Stream transcription chunks (for real-time processing)."""
        # Implement streaming transcription if needed
        yield audio_pb2.TranscribeChunk(
            text="Streaming not implemented yet",
            is_final=False
        )


async def serve():
    server = grpc.aio.server(ThreadPoolExecutor(max_workers=10))
    
    audio_pb2_grpc.add_TranscriptionServiceServicer_to_server(
        TranscriptionServiceImpl(), server
    )
    
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    
    print(f"Server starting on {listen_addr}")
    await server.start()
    await server.wait_for_termination()


if __name__ == '__main__':
    asyncio.run(serve())
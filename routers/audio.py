"""
Audio Router - Speech to Text using OpenAI Whisper
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Security, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from datetime import datetime, timezone
import os
import shutil
from typing import Optional
from openai import OpenAI

from config.settings import settings
from models.responses import StandardResponse

router = APIRouter(
    prefix="/api/audio",
    tags=["Audio"]
)

security = HTTPBearer()

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

@router.post(
    "/transcribe",
    response_model=StandardResponse[dict],
    summary="Transcribe Audio",
    description="Convert audio file to text using OpenAI Whisper",
    responses={
        200: {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "text": "Phân số là sự chia ra của một số nguyên thành các phần bằng nhau."
                        },
                        "message": "Audio transcribed successfully",
                        "createdAt": "2025-12-23T10:00:00Z"
                    }
                }
            }
        }
    }
)
async def transcribe_audio(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    **Transcribe Audio**
    
    Accepts audio files (mp3, wav, m4a, webm) and returns transcribed text.
    Max file size: 25MB (OpenAI limit)
    """
    temp_filename = None
    try:
        # Validate file type
        allowed_types = ["audio/mpeg", "audio/wav", "audio/x-m4a", "audio/webm", "audio/mp4"]
        # Note: file.content_type might not always be accurate, but good for first check
        # We can also check extensions
        ext = os.path.splitext(file.filename)[1].lower()
        allowed_exts = [".mp3", ".wav", ".m4a", ".webm", ".mp4", ".mpeg", ".mpga"]
        
        if ext not in allowed_exts:
             raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {allowed_exts}")

        # Save upload to temp file
        # Whisper API requires a file-like object with a name or a path
        temp_dir = "tmp"
        os.makedirs(temp_dir, exist_ok=True)
        temp_filename = os.path.join(temp_dir, f"audio_{int(datetime.now().timestamp())}{ext}")
        
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Call Whisper API
        with open(temp_filename, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="json",
                language="vi" # Force Vietnamese for better accuracy in our context
            )
            
        transcribed_text = transcript.text
        
        return StandardResponse(
            status="success",
            data={"text": transcribed_text},
            message="Audio transcribed successfully",
            createdAt=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        print(f"❌ Transcription failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
        
    finally:
        # Cleanup
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.remove(temp_filename)
            except:
                pass

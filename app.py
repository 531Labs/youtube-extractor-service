from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import json
import tempfile
import os
import logging
from typing import Optional, Dict, Any
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Extractor API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractRequest(BaseModel):
    url: str
    format: Optional[str] = "bestaudio"
    quality: Optional[str] = "best"

class ExtractResponse(BaseModel):
    success: bool
    url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None
    error: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "YouTube Extractor API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/extract", response_model=ExtractResponse)
async def extract_audio(request: ExtractRequest):
    """Extract audio URL from YouTube video"""
    try:
        logger.info(f"Extracting audio from: {request.url}")
        
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--format", request.format,
            "--no-warnings",
            "--quiet",
            "--print", "url",
            "--print", "title",
            "--print", "duration",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            request.url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"yt-dlp failed: {result.stderr}")
            raise HTTPException(
                status_code=400,
                detail=f"YouTube extraction failed: {result.stderr}"
            )
        
        output_lines = result.stdout.strip().split('\n')
        if len(output_lines) < 3:
            raise HTTPException(
                status_code=400,
                detail="Invalid output from yt-dlp"
            )
        
        audio_url = output_lines[0].strip()
        title = output_lines[1].strip()
        duration_str = output_lines[2].strip()
        
        duration = None
        try:
            duration = int(duration_str)
        except (ValueError, IndexError):
            logger.warning(f"Could not parse duration: {duration_str}")
        
        logger.info(f"Successfully extracted: {title}")
        
        return ExtractResponse(
            success=True,
            url=audio_url,
            title=title,
            duration=duration
        )
                
    except subprocess.TimeoutExpired:
        logger.error("yt-dlp command timed out")
        raise HTTPException(
            status_code=408,
            detail="Request timed out. YouTube may be blocking the request."
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/info")
async def get_video_info(request: ExtractRequest):
    """Get video information without downloading"""
    try:
        logger.info(f"Getting info for: {request.url}")
        
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--no-warnings",
            "--quiet",
            "--print", "title",
            "--print", "duration",
            "--print", "uploader",
            "--print", "view_count",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            request.url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get video info: {result.stderr}"
            )
        
        output_lines = result.stdout.strip().split('\n')
        if len(output_lines) < 4:
            raise HTTPException(
                status_code=400,
                detail="Invalid output from yt-dlp"
            )
        
        return {
            "success": True,
            "title": output_lines[0].strip(),
            "duration": output_lines[1].strip(),
            "uploader": output_lines[2].strip(),
            "view_count": output_lines[3].strip()
        }
        
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 
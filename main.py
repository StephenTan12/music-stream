from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import os

from audio_files_management import delete_audio_file, download_audio_file
from database import delete_audio_metadata, fetch_audio_metadata
from models import AudioMetadata
from utils import get_audio_file_location, validate_video_id

app = FastAPI()

@app.post("/songs/{video_id}")
async def download_song(video_id: str) -> AudioMetadata:
    validate_video_id(video_id)
    audio_metadata = download_audio_file(video_id)

    return audio_metadata


@app.delete("/songs/{video_id}")
async def delete_song(video_id: str):
    validate_video_id(video_id)
    
    delete_audio_metadata(video_id)
    is_success = delete_audio_file(video_id)
    
    if not is_success:
        return HTTPException(status_code=404, detail="Not found")
    return {"status": "success"}


@app.get("/songs/{video_id}")
async def get_song(video_id: str): 
    validate_video_id(video_id)
    audio_metadata = fetch_audio_metadata(video_id)

    if not audio_metadata:
        return HTTPException(status_code=404)
    return audio_metadata


@app.get("/songs/stream/{video_id}")
async def stream_song(video_id: str): 
    validate_video_id(video_id)
    file_location = get_audio_file_location(video_id)

    if not os.path.isfile(file_location):
        return HTTPException(status_code=404, detail="Not found")
    return FileResponse(file_location, media_type="audio/mp4")

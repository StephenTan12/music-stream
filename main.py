from fastapi import FastAPI

from audio_files_management import delete_audio_file, download_audio_file
from database import delete_audio_metadata
from utils import validate_video_id

app = FastAPI()

@app.post("/songs")
async def download(video_id: str):
    validate_video_id(video_id)
    audio_metadata = download_audio_file(video_id)
    return audio_metadata.model_dump()


@app.delete("/songs")
async def delete(video_id: str):
    validate_video_id(video_id)
    
    delete_audio_metadata(video_id)
    is_success = delete_audio_file(video_id)
    
    if is_success:
        return {"status": "success"}
    return {"status": "failed"}

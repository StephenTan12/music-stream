from fastapi import HTTPException
from pathlib import Path

_INCLUDED_CHARACTERS = {"_", "-"}
_SCRIPT_DIR = Path(__file__).parent
_AUDIO_FILES_DIRECTORY = f"{_SCRIPT_DIR}/audio_files"

def validate_video_id(video_id: str) -> None:
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id must contain a value")
    for char in video_id:
        if char.isalnum() or char in _INCLUDED_CHARACTERS:
            continue
        raise HTTPException(status_code=400, detail="Input contains non-alphanumeric characters")


def get_audio_file_location(video_id: str, extension: str = "m4a") -> str:
    return f"{_AUDIO_FILES_DIRECTORY}/{video_id}.{extension}"


def get_audio_files_directory() -> str:
    return _AUDIO_FILES_DIRECTORY

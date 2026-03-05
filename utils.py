import os

from fastapi import HTTPException

_INCLUDED_CHARACTERS = {"_", "-"}
_AUDIO_FILES_DIRECTORY = os.environ.get("AUDIO_FILES_DIRECTORY", "./audio_files")

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

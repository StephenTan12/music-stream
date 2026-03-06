from config import Config
from exceptions import InvalidVideoIdError

_INCLUDED_CHARACTERS = {"_", "-"}


def validate_video_id(video_id: str) -> None:
    """Validate that a video ID contains only allowed characters.
    
    Raises:
        InvalidVideoIdError: If the video ID is empty or contains invalid characters.
    """
    if not video_id:
        raise InvalidVideoIdError("video_id must contain a value")
    for char in video_id:
        if char.isalnum() or char in _INCLUDED_CHARACTERS:
            continue
        raise InvalidVideoIdError("Input contains non-alphanumeric characters")


def get_audio_file_location(video_id: str, extension: str = "m4a") -> str:
    return f"{Config.AUDIO_FILES_DIRECTORY}/{video_id}.{extension}"


def get_audio_files_directory() -> str:
    return Config.AUDIO_FILES_DIRECTORY

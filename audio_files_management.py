import os
from logging import getLogger
from pathlib import Path
from typing import Any
from yt_dlp import YoutubeDL

from database import upsert_audio_metadata
from models import AudioMetadata

_LOG = getLogger(__name__)
_YOUTUBE_URL_PREFIX = "https://youtube.com/watch?v={video_id}"
_SCRIPT_DIR = Path(__file__).parent
_AUDIO_FILES_DIRECTORY = f"{_SCRIPT_DIR}/audio_files"
_MAX_SIZE_BYTES = 7_000_000


def download_audio_file(video_id: str) -> AudioMetadata:
    options = _create_yt_options(video_id)
    video_url = _YOUTUBE_URL_PREFIX.format(video_id=video_id)
    ydl = YoutubeDL(options)

    audio_metadata = _validate_file(ydl, video_url)

    if not audio_metadata:
        raise ValueError("Video exceeds 7mb")
    
    upsert_audio_metadata(audio_metadata)
    ydl.download(video_url)

    return audio_metadata


def delete_audio_file(video_id: str) -> bool:
    audio_file_location = f"{_AUDIO_FILES_DIRECTORY}/{video_id}.m4a"
    if not os.path.isfile(audio_file_location):
        return False
    # TODO: delete metadata if stored
    os.remove(audio_file_location)
    return True


def _create_yt_options(video_id: str) -> dict[str, Any]:
    file_path = f"{_AUDIO_FILES_DIRECTORY}/{video_id}"
    yt_options = {
        "quiet": True,
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "128",
        }],
        "outtmpl": file_path + ".%(ext)s",
    }
    
    return yt_options


def _validate_file(ydl: YoutubeDL, video_url: str) -> AudioMetadata | None:
    info = ydl.extract_info(video_url, download=False)
    info = ydl.process_ie_result(info, download=False)
    info = ydl.sanitize_info(info)

    size = _estimate_entry(info, ydl)

    _LOG.info("file size is " + str(size))

    if not size or size > _MAX_SIZE_BYTES:
        return None
    return AudioMetadata.model_validate(info)


def _estimate_entry(entry, ydl: YoutubeDL, convert_bitrate_kbps: int = 128) -> int | None:
    info = ydl.process_ie_result(entry, download=False)
    info = ydl.sanitize_info(info)

    if not info:
        return None

    fmt = info.get("requested_downloads", [{}])[0].get("format", {})
    size = fmt.get("filesize") or fmt.get("filesize_approx")

    duration = info.get("duration")

    if not size and duration:
        return int((convert_bitrate_kbps * 1000 * duration) / 8)

    return None

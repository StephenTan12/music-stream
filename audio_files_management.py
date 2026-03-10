import os
from logging import getLogger
from typing import Any
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YtDlpDownloadError

from config import Config
from database import (
    add_song_to_playlist,
    get_default_playlist_id,
    upsert_audio_metadata,
)
from exceptions import DownloadError, FileTooLargeError, VideoNotFoundError
from models import AudioMetadata
from utils import get_audio_file_location, get_audio_files_directory

_LOG = getLogger(__name__)
_YOUTUBE_URL_PREFIX = "https://youtube.com/watch?v={video_id}"


def search_youtube(query: str, max_results: int = 5) -> list[str]:
    """Search YouTube and return video IDs.
    
    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default 5).
        
    Returns:
        List of video IDs, empty list if no results found.
    """
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "no_warnings": True,
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            
            if not result:
                return []
            
            entries = result.get("entries", [])
            if not entries:
                return []
            
            video_ids = [entry.get("id") for entry in entries if entry.get("id")]
            return video_ids
    except YtDlpDownloadError as e:
        _LOG.warning(f"YouTube search failed for query '{query}': {e}")
        return []


def download_audio_file(video_id: str, skip_default_playlist: bool = False) -> AudioMetadata:
    """Download audio from YouTube and save metadata.
    
    Args:
        video_id: The YouTube video ID to download.
        skip_default_playlist: If True, skip adding to "All Songs" playlist.
    
    Raises:
        FileTooLargeError: If the video exceeds the maximum file size.
        VideoNotFoundError: If the video cannot be found on YouTube.
        DownloadError: If there's an error during download.
    """
    options = _create_yt_options(video_id)
    video_url = _YOUTUBE_URL_PREFIX.format(video_id=video_id)
    ydl = YoutubeDL(options)

    try:
        audio_metadata, estimated_size = _validate_file(ydl, video_url)
    except YtDlpDownloadError as e:
        if "Video unavailable" in str(e) or "not available" in str(e).lower():
            raise VideoNotFoundError(f"Video {video_id} not found on YouTube")
        raise DownloadError(f"Failed to process video: {e}")

    if not audio_metadata:
        raise FileTooLargeError(size_bytes=estimated_size, max_bytes=Config.MAX_FILE_SIZE_BYTES)
    
    upsert_audio_metadata(audio_metadata)
    
    if not skip_default_playlist:
        add_song_to_playlist(get_default_playlist_id(), video_id)
    
    try:
        ydl.download(video_url)
    except YtDlpDownloadError as e:
        raise DownloadError(f"Failed to download video: {e}")

    return audio_metadata


def delete_audio_file(video_id: str) -> bool:
    audio_file_location = get_audio_file_location(video_id)
    if not os.path.isfile(audio_file_location):
        return False
    os.remove(audio_file_location)
    return True


def _create_yt_options(video_id: str) -> dict[str, Any]:
    file_path = f"{get_audio_files_directory()}/{video_id}"
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


def _validate_file(ydl: YoutubeDL, video_url: str) -> tuple[AudioMetadata | None, int | None]:
    """Validate video file size before downloading.
    
    Returns:
        Tuple of (AudioMetadata if valid, estimated size in bytes).
        AudioMetadata is None if file exceeds max size.
    """
    info = ydl.extract_info(video_url, download=False)
    info = ydl.process_ie_result(info, download=False)
    info = ydl.sanitize_info(info)

    size = _estimate_entry(info, ydl)

    _LOG.info(f"Estimated file size: {size} bytes")

    if not size or size > Config.MAX_FILE_SIZE_BYTES:
        return None, size
    
    if info.get("filesize") is None:
        info["filesize"] = size
    
    return AudioMetadata.model_validate(info), size


def _estimate_entry(entry: dict[str, Any], ydl: YoutubeDL, convert_bitrate_kbps: int = 128) -> int | None:
    info = ydl.process_ie_result(entry, download=False)
    info = ydl.sanitize_info(info)

    if not info:
        return None

    requested_downloads = info.get("requested_downloads", [{}])
    if requested_downloads:
        fmt = requested_downloads[0]
        size = fmt.get("filesize") or fmt.get("filesize_approx")
        if size:
            return size

    size = info.get("filesize") or info.get("filesize_approx")
    if size:
        return size

    duration = info.get("duration")
    if duration:
        return int((convert_bitrate_kbps * 1000 * duration) / 8)

    return None

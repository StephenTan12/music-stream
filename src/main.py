import asyncio
import csv
import io
import logging
import os
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from .audio_files_management import delete_audio_file, download_audio_file, search_youtube
from .database import (
    add_songs_to_playlist_batch_async,
    close_async_connection_pool,
    close_connection_pool,
    create_playlist,
    delete_audio_metadata,
    delete_playlist_async,
    fetch_all_playlists,
    fetch_audio_metadata,
    fetch_audio_metadata_paginated,
    fetch_existing_songs_batch_async,
    fetch_playlist_with_songs,
    generate_unique_playlist_name,
    get_default_playlist_id,
    init_async_connection_pool,
    init_connection_pool,
)
from .exceptions import (
    DownloadError,
    FileTooLargeError,
    InvalidVideoIdError,
    PlaylistNotFoundError,
    SongNotFoundError,
    VideoNotFoundError,
)
from .models import (
    AudioMetadata,
    FailedSong,
    PaginatedSongsResponse,
    Playlist,
    PlaylistImportResponse,
    PlaylistWithSongs,
)
from .utils import get_audio_file_location, validate_video_id

_LOG = logging.getLogger(__name__)
_MAX_CONCURRENT_DOWNLOADS = 10
_MAX_CONCURRENT_SEARCHES = 20


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown."""
    _LOG.info("Starting up: initializing connection pools...")
    init_connection_pool()
    await init_async_connection_pool()
    _LOG.info("Connection pools ready")
    
    yield
    
    _LOG.info("Shutting down: closing connection pools...")
    close_connection_pool()
    await close_async_connection_pool()
    _LOG.info("Connection pools closed")


app = FastAPI(lifespan=lifespan)


@app.exception_handler(InvalidVideoIdError)
async def invalid_video_id_handler(request: Request, exc: InvalidVideoIdError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(FileTooLargeError)
async def file_too_large_handler(request: Request, exc: FileTooLargeError) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": str(exc)})


@app.exception_handler(VideoNotFoundError)
async def video_not_found_handler(request: Request, exc: VideoNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(SongNotFoundError)
async def song_not_found_handler(request: Request, exc: SongNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DownloadError)
async def download_error_handler(request: Request, exc: DownloadError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(PlaylistNotFoundError)
async def playlist_not_found_handler(request: Request, exc: PlaylistNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/songs")
async def get_songs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
) -> PaginatedSongsResponse:
    offset = (page - 1) * page_size
    songs, total = fetch_audio_metadata_paginated(limit=page_size, offset=offset)
    total_pages = (total + page_size - 1) // page_size

    return PaginatedSongsResponse(
        songs=songs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@app.post("/songs/{video_id}")
async def download_song(video_id: str) -> AudioMetadata:
    validate_video_id(video_id)
    audio_metadata = download_audio_file(video_id)
    return audio_metadata


@app.delete("/songs/{video_id}")
async def delete_song(video_id: str) -> dict[str, str]:
    validate_video_id(video_id)
    
    delete_audio_metadata(video_id)
    is_success = delete_audio_file(video_id)
    
    if not is_success:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "success"}


@app.get("/songs/{video_id}")
async def get_song(video_id: str) -> AudioMetadata:
    validate_video_id(video_id)
    audio_metadata = fetch_audio_metadata(video_id)

    if not audio_metadata:
        raise HTTPException(status_code=404, detail="Not found")
    return audio_metadata


@app.get("/songs/stream/{video_id}")
async def stream_song(video_id: str) -> FileResponse:
    validate_video_id(video_id)
    file_location = get_audio_file_location(video_id)

    if not os.path.isfile(file_location):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(file_location, media_type="audio/mp4")


@app.get("/playlists")
async def get_playlists() -> list[Playlist]:
    playlists = fetch_all_playlists()
    return playlists


@app.get("/playlists/{playlist_id}")
async def get_playlist(playlist_id: int) -> PlaylistWithSongs:
    playlist = fetch_playlist_with_songs(playlist_id)
    
    if not playlist:
        raise PlaylistNotFoundError(f"Playlist with id {playlist_id} not found")
    
    return playlist


@app.post("/playlists/import")
async def import_playlist(file: UploadFile) -> PlaylistImportResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    text_content = content.decode("utf-8")
    
    reader = csv.DictReader(io.StringIO(text_content))
    
    if "Song" not in reader.fieldnames or "Artist" not in reader.fieldnames:
        raise HTTPException(
            status_code=400,
            detail="CSV must contain 'Song' and 'Artist' columns"
        )
    
    songs_to_import = []
    for row in reader:
        song = row.get("Song", "").strip()
        artist = row.get("Artist", "").strip()
        if song and artist:
            songs_to_import.append({"title": song, "artist": artist})
    
    if not songs_to_import:
        raise HTTPException(status_code=400, detail="No valid songs found in CSV")
    
    playlist_name = _generate_playlist_name(file.filename)
    
    try:
        playlist_id = create_playlist(playlist_name, f"Imported from {file.filename}")
    except Exception as e:
        _LOG.error(f"Failed to create playlist: {e}")
        raise HTTPException(status_code=500, detail="Failed to create playlist")
    
    try:
        result = await _process_playlist_import(playlist_id, playlist_name, songs_to_import)
        return result
    except Exception as e:
        _LOG.error(f"Import failed, rolling back playlist: {e}")
        try:
            await delete_playlist_async(playlist_id)
        except Exception as rollback_error:
            _LOG.error(f"Failed to rollback playlist: {rollback_error}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


async def _process_playlist_import(
    playlist_id: int,
    playlist_name: str,
    songs_to_import: list[dict[str, str]]
) -> PlaylistImportResponse:
    """Process the playlist import with batch operations.
    
    Args:
        playlist_id: The ID of the created playlist.
        playlist_name: The name of the playlist.
        songs_to_import: List of songs with 'title' and 'artist' keys.
        
    Returns:
        PlaylistImportResponse with import statistics.
    """
    default_playlist_id = get_default_playlist_id()
    
    search_results = await _batch_search_songs(songs_to_import)
    
    all_video_ids = list({vid for vids in search_results.values() for vid in vids})
    existing_songs = await fetch_existing_songs_batch_async(all_video_ids)
    
    songs_to_add_existing = []
    songs_to_download = []
    
    for song_info in songs_to_import:
        key = (song_info["title"], song_info["artist"])
        video_ids = search_results.get(key, [])
        
        if not video_ids:
            continue
        
        existing_found = False
        for video_id in video_ids:
            if video_id in existing_songs:
                songs_to_add_existing.append((song_info, video_id))
                existing_found = True
                break
        
        if not existing_found and video_ids:
            songs_to_download.append((song_info, video_ids))
    
    if songs_to_add_existing:
        existing_video_ids = [vid for _, vid in songs_to_add_existing]
        await add_songs_to_playlist_batch_async(playlist_id, existing_video_ids)
    
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_DOWNLOADS)
    
    async def process_download(song_info: dict[str, str], video_ids: list[str]) -> tuple[str, str, str, str | None]:
        async with semaphore:
            title = song_info["title"]
            artist = song_info["artist"]
            result, video_id = await asyncio.to_thread(_download_with_fallback, video_ids, title, artist)
            return (title, artist, result, video_id)
    
    download_tasks = [process_download(song_info, video_ids) for song_info, video_ids in songs_to_download]
    download_results = await asyncio.gather(*download_tasks)
    
    downloaded_video_ids = []
    failed_songs: list[FailedSong] = []
    
    for title, artist, result, video_id in download_results:
        if result == "imported" and video_id:
            downloaded_video_ids.append(video_id)
        else:
            failed_songs.append(FailedSong(title=title, artist=artist, reason=result))
    
    if downloaded_video_ids:
        await add_songs_to_playlist_batch_async(playlist_id, downloaded_video_ids)
        await add_songs_to_playlist_batch_async(default_playlist_id, downloaded_video_ids)
    
    imported_count = len(downloaded_video_ids)
    skipped_count = len(songs_to_add_existing)
    
    for song_info in songs_to_import:
        key = (song_info["title"], song_info["artist"])
        if key not in search_results or not search_results[key]:
            failed_songs.append(FailedSong(
                title=song_info["title"],
                artist=song_info["artist"],
                reason="Song not found on YouTube"
            ))
    
    return PlaylistImportResponse(
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        total_songs=len(songs_to_import),
        imported_count=imported_count,
        skipped_count=skipped_count,
        failed_count=len(failed_songs),
        failed_songs=failed_songs,
    )


async def _batch_search_songs(songs: list[dict[str, str]]) -> dict[tuple[str, str], list[str]]:
    """Search YouTube for multiple songs concurrently with rate limiting.
    
    Args:
        songs: List of dicts with 'title' and 'artist' keys.
        
    Returns:
        Dict mapping (title, artist) tuples to lists of video IDs.
    """
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_SEARCHES)
    
    async def search_one(song_info: dict[str, str]) -> tuple[tuple[str, str], list[str]]:
        async with semaphore:
            title = song_info["title"]
            artist = song_info["artist"]
            search_query = f"{artist} - {title} (official audio)"
            video_ids = await asyncio.to_thread(search_youtube, search_query)
            return ((title, artist), video_ids)
    
    tasks = [search_one(song_info) for song_info in songs]
    results = await asyncio.gather(*tasks)
    return dict(results)


def _download_with_fallback(video_ids: list[str], title: str, artist: str) -> tuple[str, str | None]:
    """Try downloading from a list of video IDs with retry logic.
    
    Args:
        video_ids: List of video IDs to try (in order).
        title: Song title for logging.
        artist: Song artist for logging.
        
    Returns:
        Tuple of (status, video_id). Status is "imported" on success, error message on failure.
        video_id is the successfully downloaded ID or None.
    """
    last_error = "Download failed"
    
    for video_id in video_ids:
        result = _try_download_with_retry(video_id, title, artist)
        if result == "imported":
            return ("imported", video_id)
        elif result == "skip_to_next":
            continue
        else:
            last_error = result
            continue
    
    return (last_error, None)


def _try_download_with_retry(video_id: str, title: str, artist: str) -> str:
    """Try to download a video with one retry.
    
    Args:
        video_id: The video ID to download.
        title: Song title for logging.
        artist: Song artist for logging.
    
    Returns:
        "imported" if successful.
        "skip_to_next" if should try next search result.
        Error message if fatal error.
    """
    for attempt in range(2):
        try:
            download_audio_file(video_id, skip_default_playlist=True)
            return "imported"
        except FileTooLargeError:
            return "skip_to_next"
        except VideoNotFoundError:
            return "skip_to_next"
        except DownloadError as e:
            if attempt == 0:
                _LOG.warning(f"Retry download for '{title}' by '{artist}' (video {video_id}): {e}")
                continue
            _LOG.warning(f"Trying next result for '{title}' by '{artist}': {e}")
            return "skip_to_next"
        except Exception as e:
            if attempt == 0:
                _LOG.warning(f"Retry download for '{title}' by '{artist}' (video {video_id}): {e}")
                continue
            _LOG.warning(f"Trying next result for '{title}' by '{artist}': {e}")
            return "skip_to_next"
    
    return "skip_to_next"


def _generate_playlist_name(filename: str) -> str:
    base_name = filename.rsplit(".", 1)[0]
    playlist_name = base_name.title()
    return generate_unique_playlist_name(playlist_name)

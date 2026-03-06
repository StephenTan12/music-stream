import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from audio_files_management import delete_audio_file, download_audio_file
from database import (
    delete_audio_metadata,
    fetch_all_playlists,
    fetch_audio_metadata,
    fetch_audio_metadata_paginated,
    fetch_playlist_with_songs,
)
from exceptions import (
    DownloadError,
    FileTooLargeError,
    InvalidVideoIdError,
    PlaylistNotFoundError,
    SongNotFoundError,
    VideoNotFoundError,
)
from models import AudioMetadata, PaginatedSongsResponse, Playlist, PlaylistWithSongs
from utils import get_audio_file_location, validate_video_id

app = FastAPI()


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

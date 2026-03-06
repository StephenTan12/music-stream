# Music Stream API

A FastAPI-based music streaming service that downloads audio from YouTube and serves it via REST API.

## Project Structure

```
music-stream/
├── main.py                    # FastAPI app entry point, API routes, exception handlers
├── models.py                  # Pydantic models (AudioMetadata, Playlist, PlaylistWithSongs, etc.)
├── database.py                # PostgreSQL database operations via psycopg
├── audio_files_management.py  # YouTube download logic via yt-dlp
├── utils.py                   # Validation helpers and file path utilities
├── config.py                  # Centralized configuration from environment variables
├── exceptions.py              # Custom exception classes
├── schema.sql                 # Database schema definition
├── requirements.txt           # Python dependencies
├── start.sh                   # Dev server startup script
├── audio_files/               # Downloaded audio storage (gitignored)
└── .env                       # Environment variables (gitignored)
```

## Tech Stack

- **Framework**: FastAPI with uvicorn
- **Database**: PostgreSQL via psycopg 3
- **Models**: Pydantic v2 with camelCase alias generation
- **Audio Downloads**: yt-dlp with FFmpeg post-processing to m4a
- **Environment**: python-dotenv for configuration

## API Endpoints

### Song Endpoints

| Method | Endpoint | Description | Error Codes |
|--------|----------|-------------|-------------|
| GET | `/songs` | Paginated list of songs (query params: `page`, `page_size`) | - |
| POST | `/songs/{video_id}` | Download a song from YouTube | 400, 404, 413, 502 |
| GET | `/songs/{video_id}` | Get song metadata | 400, 404 |
| DELETE | `/songs/{video_id}` | Delete a song | 400, 404 |
| GET | `/songs/stream/{video_id}` | Stream audio file | 400, 404 |

### Playlist Endpoints

| Method | Endpoint | Description | Error Codes |
|--------|----------|-------------|-------------|
| GET | `/playlists` | List all playlists | - |
| GET | `/playlists/{playlist_id}` | Get playlist with all songs | 404 |

### Error Codes
- **400**: Invalid video ID (contains non-alphanumeric characters)
- **404**: Song/video/playlist not found
- **413**: File too large (exceeds 7MB limit)
- **502**: Download error from YouTube

## Custom Exceptions

Defined in `exceptions.py`:
- `MusicStreamError` - Base exception class
- `InvalidVideoIdError` - Invalid video ID format
- `FileTooLargeError` - Video exceeds max file size
- `VideoNotFoundError` - Video not found on YouTube
- `DownloadError` - Error during download
- `SongNotFoundError` - Song not in database/filesystem
- `PlaylistNotFoundError` - Playlist not found in database

## Code Conventions

### Pydantic Models
- Use `Field(alias="...")` for database column mapping
- Apply `ConfigDict(alias_generator=to_camel, populate_by_name=True)` for camelCase JSON serialization
- Models can contain SQL generation methods (e.g., `psql_upsert_query`)
- Available models: `AudioMetadata`, `Playlist`, `PlaylistWithSongs`, `PaginatedSongsResponse`, `PaginatedPlaylistsResponse`

### Database Operations
- Use context managers for connections: `with psycopg.connect(...) as conn, conn.cursor() as cursor:`
- Use parameterized queries with `%(name)s` syntax
- Return Pydantic models from fetch operations (`AudioMetadata`, `Playlist`, `PlaylistWithSongs`)
- Use `Config.get_connection_string()` for database connection
- Available operations:
  - **Songs**: `upsert_audio_metadata()`, `fetch_audio_metadata()`, `fetch_audio_metadata_paginated()`, `delete_audio_metadata()`
  - **Playlists**: `fetch_all_playlists()`, `fetch_playlist_with_songs()`, `add_song_to_playlist()`, `remove_song_from_playlist()`, `get_default_playlist_id()`

### Video ID Validation
- Video IDs must be alphanumeric with `_` and `-` allowed
- `validate_video_id()` raises `InvalidVideoIdError` (not HTTPException)
- Exception handlers in `main.py` convert to HTTP responses

### Configuration
- All environment variables accessed via `config.Config` class
- Call `Config.validate()` at startup to check required variables
- Available settings: `POSTGRES_DATABASE`, `POSTGRES_USERNAME`, `POSTGRES_PASSWORD`, `AUDIO_FILES_DIRECTORY`, `MAX_FILE_SIZE_BYTES`

### File Storage
- Audio files stored as `{video_id}.m4a` in `AUDIO_FILES_DIRECTORY`
- Default directory: `./audio_files`
- Maximum file size: 7MB (configurable via `Config.MAX_FILE_SIZE_BYTES`)

## Environment Variables

Required in `.env`:
```
POSTGRES_DATABASE=<database_name>
POSTGRES_USERNAME=<username>
POSTGRES_PASSWORD=<password>
AUDIO_FILES_DIRECTORY=./audio_files  # optional
```

## Database Schema

See `schema.sql` for the complete schema. Initialize with:
```bash
psql -d <database_name> -f schema.sql
```

### Tables

1. **audio_files**: Stores song metadata
   - Primary key: `id` (VARCHAR, video ID)
   - Indexed on: `title`, `artist`

2. **playlists**: Stores playlist metadata
   - Primary key: `id` (SERIAL)
   - Unique constraint on `name`
   - `is_system` flag for system-managed playlists (e.g., "All Songs")
   - Indexed on: `name`, `is_system`

3. **playlist_songs**: Junction table for many-to-many relationship
   - Composite primary key: (`playlist_id`, `song_id`)
   - Foreign keys with CASCADE delete to `playlists` and `audio_files`
   - Indexed on: `playlist_id`, `song_id`

### Default Data

The schema automatically creates an "All Songs" system playlist that contains all downloaded songs. This playlist cannot be edited or deleted through the API.

## Running the Server

```bash
./start.sh
# or
uvicorn main:app --reload
```

## Playlist System

### Overview
The application includes a playlist system with automatic management of a default "All Songs" playlist.

### Behavior
- **Automatic Addition**: When a song is downloaded via `POST /songs/{video_id}`, it's automatically added to the "All Songs" playlist
- **Automatic Removal**: When a song is deleted via `DELETE /songs/{video_id}`, it's automatically removed from all playlists (via CASCADE)
- **System Playlist**: The "All Songs" playlist is marked as `is_system = true` and cannot be modified or deleted through the API
- **Read-Only Access**: Current implementation provides read-only access to playlists; no endpoints for creating, updating, or deleting playlists

### Implementation Details
- Songs are added to playlists in `audio_files_management.py` after metadata is saved
- `get_default_playlist_id()` retrieves the "All Songs" playlist ID for automatic associations
- Playlist associations are automatically cleaned up via database CASCADE constraints

## Development Guidelines

1. **Error Handling**: Raise custom exceptions from `exceptions.py`; exception handlers in `main.py` convert to HTTP responses
2. **Type Hints**: All functions must have return type annotations
3. **Imports**: Group imports by standard library, third-party, then local modules
4. **Logging**: Use `logging.getLogger(__name__)` pattern
5. **Configuration**: Access env vars via `config.Config`, never `os.environ` directly

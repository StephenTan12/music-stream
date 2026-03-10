# Music Stream API

A FastAPI-based music streaming service that downloads audio from YouTube and serves it via REST API.

## Project Structure

```
music-stream/
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point, API routes, exception handlers
│   ├── models.py                  # Pydantic models (AudioMetadata, Playlist, PlaylistWithSongs, etc.)
│   ├── database.py                # PostgreSQL database operations via psycopg
│   ├── audio_files_management.py  # YouTube download and search logic via yt-dlp
│   ├── utils.py                   # Validation helpers and file path utilities
│   ├── config.py                  # Centralized configuration from environment variables
│   └── exceptions.py              # Custom exception classes
├── schema.sql                     # Database schema definition
├── requirements.txt               # Python dependencies
├── start.sh                       # Dev server startup script
├── audio_files/                   # Downloaded audio storage (gitignored)
└── .env                           # Environment variables (gitignored)
```

## Tech Stack

- **Framework**: FastAPI with uvicorn
- **Database**: PostgreSQL via psycopg 3 with connection pooling (psycopg-pool)
- **Models**: Pydantic v2 with camelCase alias generation
- **Audio Downloads**: yt-dlp with FFmpeg post-processing to m4a
- **Environment**: python-dotenv for configuration
- **Concurrency**: Async database operations for batch imports

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
| POST | `/playlists/import` | Import playlist from Spotify CSV file | 400 |

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
- Available models: `AudioMetadata`, `Playlist`, `PlaylistWithSongs`, `PaginatedSongsResponse`, `PaginatedPlaylistsResponse`, `FailedSong`, `PlaylistImportResponse`
- `Playlist` model includes computed fields: `total_songs` (count of songs) and `total_duration` (sum of all song durations in seconds)

### Database Operations
- **Connection Pooling**: All operations use `get_connection_pool()` for sync or `get_async_connection_pool()` for async
- Pool configuration: min_size=2, max_size=20, timeout=30s
- Default playlist ID is cached in memory to avoid repeated queries
- Use context managers: `with pool.connection() as conn, conn.cursor() as cursor:`
- Use parameterized queries with `%(name)s` syntax
- Return Pydantic models from fetch operations (`AudioMetadata`, `Playlist`, `PlaylistWithSongs`)
- Available operations:
 - **Songs**: `upsert_audio_metadata()`, `fetch_audio_metadata()`, `fetch_audio_metadata_paginated()`, `delete_audio_metadata()`
 - **Playlists**: `fetch_all_playlists()`, `fetch_playlist_with_songs()`, `fetch_playlist_by_name()`, `create_playlist()`, `add_song_to_playlist()`, `remove_song_from_playlist()`, `get_default_playlist_id()`, `delete_playlist_async()`
 - **Batch Operations**: `fetch_existing_songs_batch()`, `add_songs_to_playlist_batch()`, `fetch_existing_songs_batch_async()`, `add_songs_to_playlist_batch_async()`, `generate_unique_playlist_name()`
 - **Lifecycle**: `init_connection_pool()`, `init_async_connection_pool()`, `get_connection_pool()`, `get_async_connection_pool()`, `close_connection_pool()`, `close_async_connection_pool()`

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
uvicorn src.main:app --reload
```

## Direct Database Access with psql

For administrative tasks and debugging, you can use `psql` to directly interact with the database. The database name is configured in `.env` as `POSTGRES_DATABASE`.

### Common psql Commands

Connect to the database:
```bash
psql -d <database_name>
```

Execute a single query:
```bash
psql -d <database_name> -c "SELECT * FROM playlists;"
```

### Useful Queries

**View all songs:**
```sql
SELECT id, title, artist FROM audio_files;
```

**View all playlists:**
```sql
SELECT id, name, is_system FROM playlists;
```

**View songs in a specific playlist:**
```sql
SELECT ps.song_id, af.title, af.artist 
FROM playlist_songs ps 
JOIN audio_files af ON ps.song_id = af.id 
WHERE ps.playlist_id = <playlist_id>;
```

**Remove songs from a playlist:**
```sql
DELETE FROM playlist_songs 
WHERE playlist_id = <playlist_id> 
AND song_id IN ('video_id1', 'video_id2');
```

**Find songs by title or artist:**
```sql
SELECT id, title, artist 
FROM audio_files 
WHERE title ILIKE '%search_term%' OR artist ILIKE '%search_term%';
```

**Count songs in a playlist:**
```sql
SELECT COUNT(*) FROM playlist_songs WHERE playlist_id = <playlist_id>;
```

### Notes
- Use `ILIKE` for case-insensitive pattern matching
- The `%` wildcard matches any characters in pattern searches
- Song IDs are YouTube video IDs (VARCHAR)
- Playlist IDs are auto-incrementing integers (SERIAL)

## Playlist System

### Overview
The application includes a playlist system with automatic management of a default "All Songs" playlist and support for importing playlists from Spotify CSV exports.

### Behavior
- **Automatic Addition**: When a song is downloaded via `POST /songs/{video_id}`, it's automatically added to the "All Songs" playlist
- **Automatic Removal**: When a song is deleted via `DELETE /songs/{video_id}`, it's automatically removed from all playlists (via CASCADE)
- **System Playlist**: The "All Songs" playlist is marked as `is_system = true` and cannot be modified or deleted through the API
- **Playlist Import**: Playlists can be created via `POST /playlists/import` by uploading a Spotify CSV export

### Spotify Playlist Import
The `POST /playlists/import` endpoint accepts a CSV file upload with Spotify export format:
- **CSV Parsing**: Reads `Song` and `Artist` columns from the CSV header
- **Batch YouTube Search**: All songs are searched concurrently before any downloads begin
- **Batch Existence Check**: Single database query checks which video IDs already exist
- **Playlist Naming**: Uses the CSV filename (title-cased) as playlist name; appends `(2)`, `(3)`, etc. for duplicates
- **Skip Existing**: Songs already in the database are added to the playlist via batch operation (no re-download)
- **Concurrent Downloads**: Downloads up to 10 songs concurrently (configurable via `MAX_CONCURRENT_DOWNLOADS`)
- **Rate-Limited Searches**: YouTube searches limited to 20 concurrent (configurable via `MAX_CONCURRENT_SEARCHES`)
- **Fallback Results**: Searches return up to 5 YouTube results; if one fails, tries the next result
- **Retry Logic**: Each result gets one retry before falling back to the next search result
- **Batch Playlist Addition**: All successful downloads are added to both playlists in 2 batch operations
- **Transaction Rollback**: If import fails catastrophically, the created playlist is deleted
- **Response**: Returns `PlaylistImportResponse` with counts of imported, skipped, and failed songs

### Implementation Details
- Songs can optionally skip "All Songs" addition via `skip_default_playlist` parameter in `download_audio_file()`
- `get_default_playlist_id()` caches the "All Songs" playlist ID in memory to avoid repeated queries
- `search_youtube(query, max_results=5)` in `audio_files_management.py` returns a list of video IDs from yt-dlp search
- `_batch_search_songs()` in `main.py` searches all songs concurrently before downloads begin
- `fetch_existing_songs_batch_async()` checks existence of all video IDs in a single database query
- `add_songs_to_playlist_batch_async()` adds multiple songs using PostgreSQL's UNNEST for efficient bulk insert
- `fetch_playlist_by_name()` and `create_playlist()` in `database.py` support playlist import
- Playlist associations are automatically cleaned up via database CASCADE constraints
- Connection pools are initialized once at startup via `init_connection_pool()` and `init_async_connection_pool()`
- Pools are closed on shutdown via lifespan context manager
- `get_connection_pool()` and `get_async_connection_pool()` return the initialized pools (raise if not initialized)
- `generate_unique_playlist_name()` uses a single query to find all existing names matching a pattern

## Development Guidelines

1. **Error Handling**: Raise custom exceptions from `exceptions.py`; exception handlers in `main.py` convert to HTTP responses
2. **Type Hints**: All functions must have return type annotations
3. **Imports**: Group imports by standard library, third-party, then local modules
4. **Logging**: Use `logging.getLogger(__name__)` pattern
5. **Configuration**: Access env vars via `config.Config`, never `os.environ` directly

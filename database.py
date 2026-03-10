import psycopg
from psycopg_pool import AsyncConnectionPool, ConnectionPool

from config import Config
from models import AudioMetadata, Playlist, PlaylistWithSongs

_connection_pool: ConnectionPool | None = None
_async_connection_pool: AsyncConnectionPool | None = None
_default_playlist_id_cache: int | None = None


def init_connection_pool() -> ConnectionPool:
    """Initialize the sync connection pool. Call once at startup."""
    global _connection_pool
    if _connection_pool is not None:
        raise RuntimeError("Sync connection pool already initialized")
    _connection_pool = ConnectionPool(
        conninfo=Config.get_connection_string(),
        min_size=2,
        max_size=20,
        timeout=30,
    )
    return _connection_pool


async def init_async_connection_pool() -> AsyncConnectionPool:
    """Initialize the async connection pool. Call once at startup."""
    global _async_connection_pool
    if _async_connection_pool is not None:
        raise RuntimeError("Async connection pool already initialized")
    _async_connection_pool = AsyncConnectionPool(
        conninfo=Config.get_connection_string(),
        min_size=2,
        max_size=20,
        timeout=30,
        open=False,
    )
    await _async_connection_pool.open()
    return _async_connection_pool


def get_connection_pool() -> ConnectionPool:
    """Get the sync connection pool. Must be initialized first via init_connection_pool()."""
    if _connection_pool is None:
        raise RuntimeError("Sync connection pool not initialized. Call init_connection_pool() first.")
    return _connection_pool


def get_async_connection_pool() -> AsyncConnectionPool:
    """Get the async connection pool. Must be initialized first via init_async_connection_pool()."""
    if _async_connection_pool is None:
        raise RuntimeError("Async connection pool not initialized. Call init_async_connection_pool() first.")
    return _async_connection_pool


def close_connection_pool() -> None:
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close()
        _connection_pool = None


async def close_async_connection_pool() -> None:
    global _async_connection_pool
    if _async_connection_pool is not None:
        await _async_connection_pool.close()
        _async_connection_pool = None


def upsert_audio_metadata(audio_metadata: AudioMetadata) -> None:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query, params = audio_metadata.psql_upsert_query()
        cursor.execute(query, params)
        conn.commit()


def fetch_audio_metadata(video_id: str) -> AudioMetadata | None:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = "SELECT * FROM audio_files WHERE id = %(video_id)s"
        params = {"video_id": video_id}
        cursor.execute(query, params)
        row = cursor.fetchone()

        if not row or not cursor.description:
            return None
        
        cols = [desc[0] for desc in cursor.description]
        row_dict = dict(zip(cols, row))
        
        return AudioMetadata.model_validate(row_dict)
    

def delete_audio_metadata(video_id: str) -> int:
    """Delete audio metadata from the database.
    
    Returns:
        Number of rows deleted (0 or 1).
    """
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = "DELETE FROM audio_files WHERE id = %(video_id)s"
        params = {"video_id": video_id}
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount


def fetch_audio_metadata_paginated(limit: int, offset: int) -> tuple[list[AudioMetadata], int]:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        count_query = "SELECT COUNT(*) FROM audio_files"
        cursor.execute(count_query)
        total = cursor.fetchone()[0]

        query = "SELECT * FROM audio_files ORDER BY title LIMIT %(limit)s OFFSET %(offset)s"
        params = {"limit": limit, "offset": offset}
        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows or not cursor.description:
            return [], total

        cols = [desc[0] for desc in cursor.description]
        songs = [AudioMetadata.model_validate(dict(zip(cols, row))) for row in rows]

        return songs, total


def fetch_all_playlists() -> list[Playlist]:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = "SELECT * FROM playlists ORDER BY is_system DESC, name ASC"
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows or not cursor.description:
            return []

        cols = [desc[0] for desc in cursor.description]
        playlists = [Playlist.model_validate(dict(zip(cols, row))) for row in rows]

        return playlists


def fetch_playlist_with_songs(playlist_id: int) -> PlaylistWithSongs | None:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        playlist_query = "SELECT * FROM playlists WHERE id = %(playlist_id)s"
        playlist_params = {"playlist_id": playlist_id}
        cursor.execute(playlist_query, playlist_params)
        playlist_row = cursor.fetchone()

        if not playlist_row or not cursor.description:
            return None

        playlist_cols = [desc[0] for desc in cursor.description]
        playlist_dict = dict(zip(playlist_cols, playlist_row))

        songs_query = """
            SELECT af.* FROM audio_files af
            INNER JOIN playlist_songs ps ON af.id = ps.song_id
            WHERE ps.playlist_id = %(playlist_id)s
            ORDER BY ps.added_at DESC
        """
        cursor.execute(songs_query, playlist_params)
        song_rows = cursor.fetchall()

        songs = []
        if song_rows and cursor.description:
            song_cols = [desc[0] for desc in cursor.description]
            songs = [AudioMetadata.model_validate(dict(zip(song_cols, row))) for row in song_rows]

        playlist_dict["songs"] = songs
        return PlaylistWithSongs.model_validate(playlist_dict)


def add_song_to_playlist(playlist_id: int, song_id: str) -> None:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = """
            INSERT INTO playlist_songs (playlist_id, song_id)
            VALUES (%(playlist_id)s, %(song_id)s)
            ON CONFLICT (playlist_id, song_id) DO NOTHING
        """
        params = {"playlist_id": playlist_id, "song_id": song_id}
        cursor.execute(query, params)
        conn.commit()


def remove_song_from_playlist(playlist_id: int, song_id: str) -> int:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = """
            DELETE FROM playlist_songs
            WHERE playlist_id = %(playlist_id)s AND song_id = %(song_id)s
        """
        params = {"playlist_id": playlist_id, "song_id": song_id}
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount


def get_default_playlist_id() -> int:
    global _default_playlist_id_cache
    
    if _default_playlist_id_cache is not None:
        return _default_playlist_id_cache
    
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = "SELECT id FROM playlists WHERE is_system = TRUE AND name = 'All Songs'"
        cursor.execute(query)
        row = cursor.fetchone()

        if not row:
            raise RuntimeError("Default 'All Songs' playlist not found in database")

        _default_playlist_id_cache = row[0]
        return _default_playlist_id_cache


def fetch_playlist_by_name(name: str) -> Playlist | None:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = "SELECT * FROM playlists WHERE name = %(name)s"
        params = {"name": name}
        cursor.execute(query, params)
        row = cursor.fetchone()

        if not row or not cursor.description:
            return None

        cols = [desc[0] for desc in cursor.description]
        row_dict = dict(zip(cols, row))

        return Playlist.model_validate(row_dict)


def generate_unique_playlist_name(base_name: str) -> str:
    """Generate a unique playlist name, appending (2), (3), etc. if needed.
    
    Uses a single query to find all existing names with the pattern.
    
    Args:
        base_name: The desired base name for the playlist.
        
    Returns:
        A unique playlist name.
    """
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = """
            SELECT name FROM playlists 
            WHERE name = %(base_name)s OR name LIKE %(pattern)s
        """
        pattern = f"{base_name} (%)"
        params = {"base_name": base_name, "pattern": pattern}
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            return base_name
        
        existing_names = {row[0] for row in rows}
        
        if base_name not in existing_names:
            return base_name
        
        suffix = 2
        while True:
            candidate = f"{base_name} ({suffix})"
            if candidate not in existing_names:
                return candidate
            suffix += 1


def create_playlist(name: str, description: str | None = None) -> int:
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = """
            INSERT INTO playlists (name, description, is_system)
            VALUES (%(name)s, %(description)s, FALSE)
            RETURNING id
        """
        params = {"name": name, "description": description}
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.commit()

        if not row:
            raise RuntimeError("Failed to create playlist")

        return row[0]


def fetch_existing_songs_batch(video_ids: list[str]) -> set[str]:
    """Fetch which video IDs already exist in the database.
    
    Args:
        video_ids: List of video IDs to check.
        
    Returns:
        Set of video IDs that exist in the database.
    """
    if not video_ids:
        return set()
    
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = "SELECT id FROM audio_files WHERE id = ANY(%(video_ids)s)"
        params = {"video_ids": video_ids}
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return {row[0] for row in rows}


def add_songs_to_playlist_batch(playlist_id: int, song_ids: list[str]) -> None:
    """Add multiple songs to a playlist in a single query using UNNEST.
    
    Args:
        playlist_id: The playlist ID.
        song_ids: List of song IDs to add.
    """
    if not song_ids:
        return
    
    pool = get_connection_pool()
    with pool.connection() as conn, conn.cursor() as cursor:
        query = """
            INSERT INTO playlist_songs (playlist_id, song_id)
            SELECT %(playlist_id)s, UNNEST(%(song_ids)s::text[])
            ON CONFLICT (playlist_id, song_id) DO NOTHING
        """
        params = {"playlist_id": playlist_id, "song_ids": song_ids}
        cursor.execute(query, params)
        conn.commit()


async def fetch_existing_songs_batch_async(video_ids: list[str]) -> set[str]:
    """Async version: Fetch which video IDs already exist in the database.
    
    Args:
        video_ids: List of video IDs to check.
        
    Returns:
        Set of video IDs that exist in the database.
    """
    if not video_ids:
        return set()
    
    pool = get_async_connection_pool()
    async with pool.connection() as conn, conn.cursor() as cursor:
        query = "SELECT id FROM audio_files WHERE id = ANY(%(video_ids)s)"
        params = {"video_ids": video_ids}
        await cursor.execute(query, params)
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def add_songs_to_playlist_batch_async(playlist_id: int, song_ids: list[str]) -> None:
    """Async version: Add multiple songs to a playlist using UNNEST.
    
    Args:
        playlist_id: The playlist ID.
        song_ids: List of song IDs to add.
    """
    if not song_ids:
        return
    
    pool = get_async_connection_pool()
    async with pool.connection() as conn, conn.cursor() as cursor:
        query = """
            INSERT INTO playlist_songs (playlist_id, song_id)
            SELECT %(playlist_id)s, UNNEST(%(song_ids)s::text[])
            ON CONFLICT (playlist_id, song_id) DO NOTHING
        """
        params = {"playlist_id": playlist_id, "song_ids": song_ids}
        await cursor.execute(query, params)
        await conn.commit()


async def delete_playlist_async(playlist_id: int) -> None:
    """Delete a playlist (for rollback on import failure).
    
    Args:
        playlist_id: The playlist ID to delete.
    """
    pool = get_async_connection_pool()
    async with pool.connection() as conn, conn.cursor() as cursor:
        query = "DELETE FROM playlists WHERE id = %(playlist_id)s"
        params = {"playlist_id": playlist_id}
        await cursor.execute(query, params)
        await conn.commit()

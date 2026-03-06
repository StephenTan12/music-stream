import psycopg

from config import Config
from models import AudioMetadata, Playlist, PlaylistWithSongs


def upsert_audio_metadata(audio_metadata: AudioMetadata) -> None:
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
        query, params = audio_metadata.psql_upsert_query()
        cursor.execute(query, params)
        conn.commit()


def fetch_audio_metadata(video_id: str) -> AudioMetadata | None:
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
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
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
        query = "DELETE FROM audio_files WHERE id = %(video_id)s"
        params = {"video_id": video_id}
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount


def fetch_audio_metadata_paginated(limit: int, offset: int) -> tuple[list[AudioMetadata], int]:
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
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
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
        query = "SELECT * FROM playlists ORDER BY is_system DESC, name ASC"
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows or not cursor.description:
            return []

        cols = [desc[0] for desc in cursor.description]
        playlists = [Playlist.model_validate(dict(zip(cols, row))) for row in rows]

        return playlists


def fetch_playlist_with_songs(playlist_id: int) -> PlaylistWithSongs | None:
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
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
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
        query = """
            INSERT INTO playlist_songs (playlist_id, song_id)
            VALUES (%(playlist_id)s, %(song_id)s)
            ON CONFLICT (playlist_id, song_id) DO NOTHING
        """
        params = {"playlist_id": playlist_id, "song_id": song_id}
        cursor.execute(query, params)
        conn.commit()


def remove_song_from_playlist(playlist_id: int, song_id: str) -> int:
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
        query = """
            DELETE FROM playlist_songs
            WHERE playlist_id = %(playlist_id)s AND song_id = %(song_id)s
        """
        params = {"playlist_id": playlist_id, "song_id": song_id}
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount


def get_default_playlist_id() -> int:
    with (
        psycopg.connect(Config.get_connection_string()) as conn,
        conn.cursor() as cursor
    ):
        query = "SELECT id FROM playlists WHERE is_system = TRUE AND name = 'All Songs'"
        cursor.execute(query)
        row = cursor.fetchone()

        if not row:
            raise RuntimeError("Default 'All Songs' playlist not found in database")

        return row[0]

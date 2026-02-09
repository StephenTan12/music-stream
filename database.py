from dotenv import load_dotenv
import os
import psycopg

from models import AudioMetadata

load_dotenv()

_DATABASE = os.getenv("POSTGRES_DATABASE")
_USERNAME = os.getenv("POSTGRES_USERNAME")
_PASSWORD = os.getenv("POSTGRES_PASSWORD")
_CONNECTION_STR = f"dbname={_DATABASE} user={_USERNAME} password={_PASSWORD}"


def upsert_audio_metadata(audio_metadata: AudioMetadata):
    with (
        psycopg.connect(_CONNECTION_STR) as conn,
        conn.cursor() as cursor
    ):
        query, params= audio_metadata.psql_upsert_query()
        cursor.execute(query, params)
        conn.commit()


def fetch_audio_metadata(video_id: str) -> AudioMetadata | None:
    with (
        psycopg.connect(_CONNECTION_STR) as conn,
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
    

def delete_audio_metadata(video_id: str):
    with (
        psycopg.connect(_CONNECTION_STR) as conn,
        conn.cursor() as cursor
    ):
        query = "DELETE FROM audio_files WHERE id = %(video_id)s"
        params = {"video_id": video_id}
        cursor.execute(query, params)
        conn.commit()

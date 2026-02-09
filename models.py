from psycopg import sql
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Any


class AudioMetadata(BaseModel):
    id: str = Field(alias="id")
    title: str = Field(alias="title")
    duration: int = Field(alias="duration")
    tags: list[str] = Field(alias="tags")
    full_title: str = Field(alias="fulltitle")
    file_size: int = Field(alias="filesize")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def psql_upsert_query(self) -> tuple[sql.SQL, dict[str, Any]]:
        query = sql.SQL("""
            INSERT INTO audio_files (id, title, duration, tags, full_title, file_size)
            VALUES (%(id)s, %(title)s, %(duration)s, %(tags)s, %(full_title)s, %(file_size)s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                duration = EXCLUDED.duration,
                tags = EXCLUDED.tags,
                full_title = EXCLUDED.full_title,
                file_size = EXCLUDED.file_size;
        """)
        
        return query, self.model_dump()


class SongPlaylist(BaseModel):
    id: str
    title: str
    total_duration: int
    song_ids: list[str]

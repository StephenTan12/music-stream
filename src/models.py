from datetime import datetime
from psycopg import sql
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from typing import Any


class AudioMetadata(BaseModel):
    id: str = Field(alias="id")
    title: str = Field(alias="title")
    artist: str | None = Field(alias="artist", default=None)

    @field_validator("artist", mode="before")
    @classmethod
    def parse_first_artist(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.split(",")[0].strip()
    duration: int = Field(alias="duration")
    tags: list[str] = Field(alias="tags")
    full_title: str = Field(alias="fulltitle")
    file_size: int = Field(alias="filesize")

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    def psql_upsert_query(self) -> tuple[sql.SQL, dict[str, Any]]:
        query = sql.SQL("""
            INSERT INTO audio_files (id, title, artist, duration, tags, full_title, file_size)
            VALUES (%(id)s, %(title)s, %(artist)s, %(duration)s, %(tags)s, %(full_title)s, %(file_size)s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                artist = EXCLUDED.artist,
                duration = EXCLUDED.duration,
                tags = EXCLUDED.tags,
                full_title = EXCLUDED.full_title,
                file_size = EXCLUDED.file_size;
        """)
        
        return query, self.model_dump()


class PaginatedSongsResponse(BaseModel):
    songs: list[AudioMetadata]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Playlist(BaseModel):
    id: int = Field(alias="id")
    name: str = Field(alias="name")
    description: str | None = Field(alias="description", default=None)
    is_system: bool = Field(alias="is_system")
    created_at: datetime = Field(alias="created_at")
    updated_at: datetime = Field(alias="updated_at")
    total_songs: int = Field(alias="total_songs", default=0)
    total_duration: int = Field(alias="total_duration", default=0)

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PlaylistWithSongs(Playlist):
    songs: list[AudioMetadata]


class PaginatedPlaylistsResponse(BaseModel):
    playlists: list[Playlist]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class FailedSong(BaseModel):
    title: str
    artist: str
    reason: str

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PlaylistImportResponse(BaseModel):
    playlist_id: int
    playlist_name: str
    total_songs: int
    imported_count: int
    skipped_count: int
    failed_count: int
    failed_songs: list[FailedSong]

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

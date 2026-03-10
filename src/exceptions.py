class MusicStreamError(Exception):
    """Base exception for music-stream application."""
    pass


class InvalidVideoIdError(MusicStreamError):
    """Raised when a video ID contains invalid characters or is empty."""
    pass


class FileTooLargeError(MusicStreamError):
    """Raised when a video file exceeds the maximum allowed size."""
    def __init__(self, size_bytes: int | None = None, max_bytes: int | None = None):
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        message = "Video file exceeds maximum allowed size"
        if max_bytes:
            message = f"Video file exceeds maximum allowed size of {max_bytes // 1_000_000}MB"
        super().__init__(message)


class VideoNotFoundError(MusicStreamError):
    """Raised when a video cannot be found on YouTube."""
    pass


class DownloadError(MusicStreamError):
    """Raised when there's an error downloading the video."""
    pass


class SongNotFoundError(MusicStreamError):
    """Raised when a song is not found in the database or filesystem."""
    pass


class PlaylistNotFoundError(MusicStreamError):
    """Raised when a playlist is not found in the database."""
    pass

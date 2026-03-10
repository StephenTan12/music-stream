from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    POSTGRES_DATABASE: str = os.environ.get("POSTGRES_DATABASE", "")
    POSTGRES_USERNAME: str = os.environ.get("POSTGRES_USERNAME", "")
    POSTGRES_PASSWORD: str = os.environ.get("POSTGRES_PASSWORD", "")
    AUDIO_FILES_DIRECTORY: str = os.environ.get("AUDIO_FILES_DIRECTORY", "./audio_files")
    MAX_FILE_SIZE_BYTES: int = 7_000_000

    @classmethod
    def get_connection_string(cls) -> str:
        return f"dbname={cls.POSTGRES_DATABASE} user={cls.POSTGRES_USERNAME} password={cls.POSTGRES_PASSWORD}"

    @classmethod
    def validate(cls) -> None:
        missing = []
        if not cls.POSTGRES_DATABASE:
            missing.append("POSTGRES_DATABASE")
        if not cls.POSTGRES_USERNAME:
            missing.append("POSTGRES_USERNAME")
        if not cls.POSTGRES_PASSWORD:
            missing.append("POSTGRES_PASSWORD")
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

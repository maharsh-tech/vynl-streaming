import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PORT: int = int(os.getenv("PORT", "8000"))
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    ITUNES_SEARCH_COUNTRY: str = os.getenv("ITUNES_SEARCH_COUNTRY", "US")
    ITUNES_SEARCH_LIMIT: int = int(os.getenv("ITUNES_SEARCH_LIMIT", "5"))
    DOWNLOAD_FILE_TTL: int = int(os.getenv("DOWNLOAD_FILE_TTL", "900"))
    APL_MAX_RETRIES: int = int(os.getenv("APL_MAX_RETRIES", "3"))


settings = Settings()

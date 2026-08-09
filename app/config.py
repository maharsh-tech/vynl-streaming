import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PORT: int = int(os.getenv("PORT", "8000"))
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")
    ITUNES_SEARCH_COUNTRY: str = os.getenv("ITUNES_SEARCH_COUNTRY", "US")
    ITUNES_SEARCH_LIMIT: int = int(os.getenv("ITUNES_SEARCH_LIMIT", "5"))
    APL_MAX_RETRIES: int = int(os.getenv("APL_MAX_RETRIES", "3"))
    DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))


settings = Settings()

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

    API_ID: int | None = int(os.getenv("API_ID")) if os.getenv("API_ID") else None
    API_HASH: str | None = os.getenv("API_HASH")
    BOT_TOKEN: str | None = os.getenv("BOT_TOKEN")
    STORAGE_CHANNEL_ID: int | None = (
        int(os.getenv("STORAGE_CHANNEL_ID")) if os.getenv("STORAGE_CHANNEL_ID") else None
    )

    def telegram_configured(self) -> bool:
        return all(
            [
                self.API_ID,
                self.API_HASH,
                self.BOT_TOKEN,
                self.STORAGE_CHANNEL_ID,
            ]
        )


settings = Settings()

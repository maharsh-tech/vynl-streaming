from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.tracks import router as tracks_router
from app.config import settings
from app.services import telegram_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.telegram_configured():
        await telegram_storage.start_client()
    yield
    if settings.telegram_configured():
        await telegram_storage.stop_client()


app = FastAPI(title="vynl-audio-streaming", lifespan=lifespan)

app.include_router(tracks_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.tracks import router as tracks_router
from app.api.stream import router as stream_router
from app.config import settings
from app.db import mongo
from app.services import telegram_uploader


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.mongo_configured():
        await mongo.connect()
    if settings.telegram_configured():
        await telegram_uploader.start_client()
    yield
    await telegram_uploader.stop_client()
    await mongo.disconnect()


app = FastAPI(title="vynl-audio-streaming", lifespan=lifespan)

app.include_router(tracks_router, prefix="/api/v1")
app.include_router(stream_router)  # /stream/{token}/{filename} — no prefix


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mongo": settings.mongo_configured(),
        "telegram": settings.telegram_configured(),
    }

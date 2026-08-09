import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.tracks import router as tracks_router
from app.services import download_cache

_cleanup_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cleanup_task
    _cleanup_task = asyncio.create_task(download_cache.run_cleanup_loop())
    yield
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="vynl-audio-streaming", lifespan=lifespan)

app.include_router(tracks_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}

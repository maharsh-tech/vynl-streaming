from fastapi import FastAPI

from app.api.tracks import router as tracks_router

app = FastAPI(title="vynl-audio-streaming")

app.include_router(tracks_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}

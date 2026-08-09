import tempfile
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.exceptions import (
    DownloadError,
    FileNotReadyError,
    MultiTrackError,
    TrackNotFoundError,
)
from app.models.track import (
    DownloadRequest,
    DownloadResponse,
    ResolveRequest,
    ResolveResponse,
    SearchCandidate,
)
from app.services import download_cache, track_resolver
from app.services.apple_downloader import download_track

router = APIRouter(tags=["tracks"])


@router.post("/tracks/resolve", response_model=ResolveResponse)
async def resolve_track(body: ResolveRequest) -> ResolveResponse:
    try:
        return await track_resolver.resolve_track(body.title, body.artist)
    except TrackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tracks/search", response_model=list[SearchCandidate])
async def search_tracks(
    title: str = Query(..., min_length=1),
    artist: str | None = Query(None),
) -> list[SearchCandidate]:
    results = await track_resolver.search_tracks(title, artist)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No Apple Music matches for: {title}",
        )
    return results


@router.post("/tracks/download", response_model=DownloadResponse)
async def download_track_route(body: DownloadRequest) -> DownloadResponse:
    resolved: ResolveResponse | None = None
    apple_music_url = body.apple_music_url

    try:
        if not apple_music_url:
            resolved = await track_resolver.resolve_track(body.title, body.artist)
            apple_music_url = resolved.apple_music_url

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = await download_track(apple_music_url, tmp_dir)
            cached = await download_cache.store(result)

        return DownloadResponse(
            title=result.title,
            artist=resolved.artist if resolved else body.artist,
            filename=result.filename,
            file_size=result.file_size,
            apple_track_id=resolved.apple_track_id if resolved else None,
            apple_music_url=apple_music_url,
            download_url=f"/api/v1/tracks/download/file/{cached.token}",
            expires_at=cached.expires_at,
            artwork_url=resolved.artwork_url if resolved else None,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TrackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MultiTrackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/tracks/download/file/{token}")
async def download_track_file(token: str) -> FileResponse:
    try:
        cached = await download_cache.get(token)
    except FileNotReadyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(
        path=cached.audio_path,
        media_type="audio/mpeg",
        filename=cached.filename,
    )

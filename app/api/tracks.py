import asyncio
import shutil
import tempfile

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.config import settings
from app.config import settings
from app.exceptions import (
    DownloadError,
    MultiTrackError,
    TrackNotFoundError,
)
from app.models.track import (
    DownloadRequest,
    ResolveRequest,
    ResolveResponse,
    SearchCandidate,
)
from app.services import telegram_storage, track_resolver
from app.services.apple_downloader import download_track

router = APIRouter(tags=["tracks"])


def _cleanup_temp_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


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


@router.post("/tracks/download")
async def download_track_route(body: DownloadRequest) -> FileResponse:
    """
    Resolve (if needed) → download MP3 → upload to Telegram → return the file.

    Temp stream URLs come from Telegram in Phase 4. This endpoint returns the
    raw MP3 file directly for testing.
    """
    apple_music_url = body.apple_music_url

    if not settings.telegram_configured():
        raise HTTPException(
            status_code=503,
            detail="Telegram not configured. Add API_ID, API_HASH, BOT_TOKEN, STORAGE_CHANNEL_ID to .env",
        )

    try:
        if not apple_music_url:
            if not body.title or not body.title.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Provide title or apple_music_url",
                )
            resolved = await track_resolver.resolve_track(body.title, body.artist)
            apple_music_url = resolved.apple_music_url

        tmp_dir = tempfile.mkdtemp(prefix="vynl-dl-")
        try:
            result = await asyncio.wait_for(
                download_track(apple_music_url, tmp_dir),
                timeout=settings.DOWNLOAD_TIMEOUT,
            )
            telegram_ref = await telegram_storage.upload_audio(
                audio_path=result.audio_path,
                title=result.title,
                filename=result.filename,
                thumb_path=result.thumb_path,
            )
        except Exception:
            _cleanup_temp_dir(tmp_dir)
            raise

        headers = {
            "X-Apple-Music-Url": apple_music_url,
            "X-Telegram-Chat-Id": telegram_ref.chat_id,
            "X-Telegram-Msg-Id": str(telegram_ref.msg_id),
            "X-Telegram-File-Hash": telegram_ref.hash,
        }

        return FileResponse(
            path=result.audio_path,
            media_type="audio/mpeg",
            filename=result.filename,
            headers=headers,
            background=BackgroundTask(_cleanup_temp_dir, tmp_dir),
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Download timed out after {settings.DOWNLOAD_TIMEOUT}s",
        ) from exc
    except TrackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MultiTrackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

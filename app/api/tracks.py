import asyncio
import shutil
import tempfile

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pymongo.errors import DuplicateKeyError
from starlette.background import BackgroundTask

from app.config import settings
from app.db import mongo
from app.exceptions import (
    DownloadError,
    MultiTrackError,
    ServiceUnavailableError,
    StorageError,
    TrackNotFoundError,
)
from app.models.track import (
    IngestRequest,
    IngestResponse,
    ResolveRequest,
    ResolveResponse,
    SearchCandidate,
    StreamLinkResponse,
)
from app.services import track_resolver
from app.services.apple_downloader import download_track
from app.services import telegram_uploader, token_service

router = APIRouter(tags=["tracks"])


def _cleanup_temp_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _require_storage() -> None:
    if not settings.telegram_configured() or not settings.mongo_configured():
        raise ServiceUnavailableError(
            "Telegram and MongoDB must be configured for ingest"
        )


# ── Phase 1 ───────────────────────────────────────────────────────────────────

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


# ── Phase 3: Ingest ───────────────────────────────────────────────────────────

@router.post("/tracks/ingest", response_model=IngestResponse)
async def ingest_track(body: IngestRequest) -> IngestResponse:
    """
    Resolve → dedup → download → upload to Telegram → save in MongoDB.
    Returns immediately on dedup hit (fast). First ingest takes 10-30+ s.
    """
    try:
        _require_storage()
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        # 1. Resolve
        if body.title:
            resolved = await track_resolver.resolve_track(body.title, body.artist)
            apple_track_id = resolved.apple_track_id
            apple_music_url = resolved.apple_music_url
            title = resolved.title
            artist = resolved.artist
            duration_ms = resolved.duration_ms
            artwork_url = resolved.artwork_url
        else:
            # URL path — apple_track_id required for dedup
            if not body.apple_track_id:
                raise HTTPException(
                    status_code=400,
                    detail="apple_track_id is required when using apple_music_url directly",
                )
            apple_track_id = body.apple_track_id
            apple_music_url = body.apple_music_url  # type: ignore[assignment]
            title = body.title or ""
            artist = body.artist or ""
            duration_ms = None
            artwork_url = None

        # 2. Dedup
        existing = await mongo.find_track_by_apple_id(apple_track_id)
        if existing:
            return IngestResponse(
                track_id=existing["track_id"],
                title=existing["title"],
                artist=existing["artist"],
                apple_track_id=existing["apple_track_id"],
                apple_music_url=existing["apple_music_url"],
                filename=existing["filename"],
                file_size=existing["file_size"],
                duration_ms=existing.get("duration_ms"),
                artwork_url=existing.get("artwork_url"),
                status=existing["status"],
                deduped=True,
            )

        # 3. Download
        tmp_dir = tempfile.mkdtemp(prefix="vynl-ingest-")
        try:
            dl = await asyncio.wait_for(
                download_track(apple_music_url, tmp_dir),
                timeout=settings.DOWNLOAD_TIMEOUT,
            )

            # 4. Upload to Telegram
            tg_ref = await telegram_uploader.upload_audio(
                audio_path=dl.audio_path,
                title=dl.title,
                filename=dl.filename,
                thumb_path=dl.thumb_path,
                performer=artist,
            )
        finally:
            _cleanup_temp_dir(tmp_dir)

        # 5. Save to MongoDB
        doc = {
            "apple_track_id": apple_track_id,
            "apple_music_url": apple_music_url,
            "title": dl.title or title,
            "artist": artist,
            "filename": dl.filename,
            "file_size": dl.file_size,
            "duration_ms": duration_ms,
            "artwork_url": artwork_url,
            "telegram": {
                "chat_id": tg_ref.chat_id,
                "msg_id": tg_ref.msg_id,
                "file_id": tg_ref.file_id,
            },
            "status": "stored",
        }
        try:
            saved = await mongo.insert_track(doc)
        except DuplicateKeyError:
            # Race: another request stored it concurrently — return deduped
            existing = await mongo.find_track_by_apple_id(apple_track_id)
            return IngestResponse(
                track_id=existing["track_id"],
                title=existing["title"],
                artist=existing["artist"],
                apple_track_id=existing["apple_track_id"],
                apple_music_url=existing["apple_music_url"],
                filename=existing["filename"],
                file_size=existing["file_size"],
                duration_ms=existing.get("duration_ms"),
                artwork_url=existing.get("artwork_url"),
                status=existing["status"],
                deduped=True,
            )

        return IngestResponse(
            track_id=saved["track_id"],
            title=saved["title"],
            artist=saved["artist"],
            apple_track_id=saved["apple_track_id"],
            apple_music_url=saved["apple_music_url"],
            filename=saved["filename"],
            file_size=saved["file_size"],
            duration_ms=saved.get("duration_ms"),
            artwork_url=saved.get("artwork_url"),
            status=saved["status"],
            deduped=False,
        )

    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Download timed out") from exc
    except TrackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MultiTrackError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (StorageError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ── Phase 4: Stream link ──────────────────────────────────────────────────────

@router.get("/tracks/{track_id}/stream-link", response_model=StreamLinkResponse)
async def get_stream_link(track_id: str) -> StreamLinkResponse:
    """Issue a time-limited stream URL for a stored track."""
    try:
        _require_storage()
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    doc = await mongo.find_track_by_id(track_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Track not found: {track_id}")

    token, expires_at = await token_service.create_token(track_id)
    filename = doc.get("filename", "audio.mp3")
    stream_url = f"{settings.BASE_URL}/stream/{token}/{filename}"

    return StreamLinkResponse(
        stream_url=stream_url,
        expires_at=expires_at,
        ttl_seconds=settings.STREAM_TOKEN_TTL,
    )

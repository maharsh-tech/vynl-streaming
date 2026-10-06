"""Stream endpoint — serve audio bytes from Telegram with Range support."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.db import mongo
from app.services import streamer, token_service

router = APIRouter()


@router.get("/stream/{token}/{filename}")
async def stream_audio(token: str, filename: str, request: Request):
    """
    Play audio from Telegram storage.
    Validates the token TTL, then proxies bytes with Range support.
    """
    token_doc = await token_service.validate_token(token)
    if not token_doc:
        raise HTTPException(status_code=410, detail="Stream link expired or invalid")

    track = await mongo.find_track_by_id(token_doc["track_id"])
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    tg = track["telegram"]
    chat_id: int = tg["chat_id"]
    msg_id: int = tg["msg_id"]

    range_header: str | None = request.headers.get("range")

    try:
        # We need file size for Content-Range — get it from a quick message fetch
        from app.services.telegram_uploader import _client
        if _client is None or not _client.is_connected:
            raise HTTPException(status_code=503, detail="Telegram client not available")

        msg = await _client.get_messages(chat_id, msg_id)
        if not msg or not msg.audio:
            raise HTTPException(status_code=404, detail="Audio not found in Telegram")

        file_size: int = msg.audio.file_size
        start, end = streamer._parse_range(range_header, file_size)
        content_length = end - start + 1

        headers = {
            "Content-Type": "audio/mpeg",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Range": f"bytes {start}-{end}/{file_size}",
        }
        status = 206 if range_header else 200

        return StreamingResponse(
            streamer.stream_audio(chat_id, msg_id, range_header),
            status_code=status,
            headers=headers,
            media_type="audio/mpeg",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stream error: {exc}") from exc

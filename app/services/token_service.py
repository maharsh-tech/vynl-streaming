"""Token service — issue and validate time-limited stream tokens."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db import mongo


async def create_token(track_id: str) -> tuple[str, datetime]:
    """
    Mint a new URL-safe token with TTL from settings.STREAM_TOKEN_TTL.
    Returns (token, expires_at).
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=settings.STREAM_TOKEN_TTL)
    await mongo.insert_token(token, track_id, expires_at)
    return token, expires_at


async def validate_token(token: str) -> dict | None:
    """Returns the token doc if valid and not expired, else None."""
    return await mongo.find_valid_token(token)

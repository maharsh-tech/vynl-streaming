"""MongoDB client and collection helpers (Motor async driver)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


async def connect() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGO_URI)
    _db = _client[settings.MONGO_DB]
    # Ensure indexes (idempotent)
    tracks = _db["tracks"]
    await tracks.create_index("track_id", unique=True)
    await tracks.create_index("apple_track_id", unique=True)
    await tracks.create_index("status")

    tokens = _db["stream_tokens"]
    await tokens.create_index("token", unique=True)
    await tokens.create_index("track_id")
    # TTL index — Mongo auto-deletes expired tokens
    await tokens.create_index("expires_at", expireAfterSeconds=0)


async def disconnect() -> None:
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None


def _get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not connected")
    return _db


# ── Tracks ────────────────────────────────────────────────────────────────────

async def find_track_by_apple_id(apple_track_id: int) -> dict | None:
    return await _get_db()["tracks"].find_one(
        {"apple_track_id": apple_track_id}, {"_id": 0}
    )


async def find_track_by_id(track_id: str) -> dict | None:
    return await _get_db()["tracks"].find_one({"track_id": track_id}, {"_id": 0})


async def insert_track(doc: dict) -> dict:
    """Insert a track and return it. Caller must set track_id + timestamps."""
    if "track_id" not in doc:
        doc["track_id"] = str(uuid.uuid4())
    now = _now()
    doc.setdefault("created_at", now)
    doc.setdefault("updated_at", now)
    await _get_db()["tracks"].insert_one(doc)
    doc.pop("_id", None)
    return doc


# ── Stream tokens ─────────────────────────────────────────────────────────────

async def insert_token(token: str, track_id: str, expires_at: datetime) -> None:
    await _get_db()["stream_tokens"].insert_one(
        {
            "token": token,
            "track_id": track_id,
            "expires_at": expires_at,
            "created_at": _now(),
        }
    )


async def find_valid_token(token: str) -> dict | None:
    """Returns token doc only if not expired (TTL index may not fire instantly)."""
    doc = await _get_db()["stream_tokens"].find_one({"token": token}, {"_id": 0})
    if doc and doc["expires_at"] > _now():
        return doc
    return None

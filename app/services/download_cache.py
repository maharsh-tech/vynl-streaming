import asyncio
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.exceptions import FileNotReadyError
from app.services.apple_downloader import DownloadResult

_cache_root = Path(__file__).resolve().parent.parent.parent / ".download_cache"
_entries: dict[str, "CachedDownload"] = {}
_lock = asyncio.Lock()


@dataclass
class CachedDownload:
    token: str
    audio_path: Path
    filename: str
    file_size: int
    expires_at: datetime


async def store(result: DownloadResult) -> CachedDownload:
    token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.DOWNLOAD_FILE_TTL)
    cache_dir = _cache_root / token
    cache_dir.mkdir(parents=True, exist_ok=True)

    dest = cache_dir / result.filename
    shutil.copy2(result.audio_path, dest)
    if result.thumb_path:
        shutil.copy2(result.thumb_path, cache_dir / "cover.jpg")

    cached = CachedDownload(
        token=token,
        audio_path=dest,
        filename=result.filename,
        file_size=result.file_size,
        expires_at=expires_at,
    )

    async with _lock:
        _entries[token] = cached

    return cached


async def get(token: str) -> CachedDownload:
    async with _lock:
        cached = _entries.get(token)
        if cached is None:
            raise FileNotReadyError("Download token not found or expired")
        if datetime.now(timezone.utc) >= cached.expires_at:
            await _remove_entry(token)
            raise FileNotReadyError("Download token not found or expired")
        return cached


async def _remove_entry(token: str) -> None:
    cached = _entries.pop(token, None)
    if cached is None:
        return
    cache_dir = cached.audio_path.parent
    shutil.rmtree(cache_dir, ignore_errors=True)


async def cleanup_expired() -> None:
    now = datetime.now(timezone.utc)
    async with _lock:
        expired = [token for token, entry in _entries.items() if now >= entry.expires_at]
        for token in expired:
            await _remove_entry(token)


async def run_cleanup_loop(interval_seconds: int = 60) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        await cleanup_expired()

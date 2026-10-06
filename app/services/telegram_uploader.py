"""Telegram storage: upload audio to private channel via wzgram (pyrogram drop-in)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from wzgram import Client
from wzgram.errors import FloodWait

from app.config import settings

_client: Client | None = None
# ponytail: single upload at a time — ceiling is throughput. Upgrade: remove semaphore + use queue if parallel ingests needed.
_upload_sem = asyncio.Semaphore(1)


@dataclass
class TelegramFileRef:
    chat_id: int
    msg_id: int
    file_id: str  # first 20 chars of file_unique_id — enough to identify


async def start_client() -> None:
    global _client
    _client = Client(
        name="vynl_storage",
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        bot_token=settings.BOT_TOKEN,
        in_memory=True,  # no session file on disk
    )
    await _client.start()


async def stop_client() -> None:
    global _client
    if _client and _client.is_connected:
        await _client.stop()
    _client = None


async def upload_audio(
    audio_path: str,
    title: str,
    filename: str,
    thumb_path: str | None = None,
    performer: str | None = None,
) -> TelegramFileRef:
    if _client is None or not _client.is_connected:
        raise RuntimeError("Telegram client is not started")

    async with _upload_sem:
        msg = await _flood_safe(
            _client.send_audio,
            chat_id=settings.STORAGE_CHANNEL_ID,
            audio=audio_path,
            thumb=thumb_path,
            title=title,
            file_name=filename,
            performer=performer or "",
        )
        return TelegramFileRef(
            chat_id=msg.chat.id,
            msg_id=msg.id,
            file_id=msg.audio.file_unique_id[:20],
        )


async def _flood_safe(func, *args, **kwargs):
    while True:
        try:
            return await func(*args, **kwargs)
        except FloodWait as e:
            wait = e.value + 1
            print(f"[TG FloodWait] sleeping {wait}s")
            await asyncio.sleep(wait)

"""
Byte-range streaming proxy from Telegram.

Uses Pyrogram/wzgram download_media() which is guaranteed to exist.
Streams the file in 1 MB chunks, honoring Range headers for seek support.

ponytail: downloads sequentially from Telegram — no DC-aware multi-client pooling.
Ceiling: all stream requests share one bot's bandwidth from one DC.
Upgrade: add MULTI_TOKEN bot pool (Falix pattern) if throughput is insufficient.
"""
from __future__ import annotations

import io
import re
from typing import AsyncGenerator

from app.services.telegram_uploader import _client

CHUNK_SIZE = 1 * 1024 * 1024  # 1 MB


def _parse_range(range_header: str | None, file_size: int) -> tuple[int, int]:
    """Parse Range header, return (start, end) inclusive byte offsets."""
    if not range_header:
        return 0, file_size - 1
    m = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not m:
        return 0, file_size - 1
    start_s, end_s = m.group(1), m.group(2)
    start = int(start_s) if start_s else 0
    end = int(end_s) if end_s else file_size - 1
    end = min(end, file_size - 1)
    return start, end


async def stream_audio(
    chat_id: int,
    msg_id: int,
    range_header: str | None = None,
) -> AsyncGenerator[bytes, None]:
    """
    Yield audio bytes from a Telegram message.
    Downloads via download_media into BytesIO, then slices for Range.
    """
    client = _client  # type: ignore[assignment]
    if client is None or not client.is_connected:
        raise RuntimeError("Telegram client not connected")

    msg = await client.get_messages(chat_id, msg_id)
    if not msg or not msg.audio:
        raise ValueError(f"No audio in message {msg_id}")

    file_size: int = msg.audio.file_size
    start, end = _parse_range(range_header, file_size)

    # Download to in-memory buffer
    # ponytail: downloads entire file to RAM for range slicing.
    # Ceiling: large files (>100 MB) will be slow + memory-heavy.
    # Upgrade: use Pyrogram's internal get_file iterator with offset param.
    buf = io.BytesIO()
    await client.download_media(msg, file_name=buf)
    buf.seek(start)

    remaining = end - start + 1
    while remaining > 0:
        chunk = buf.read(min(CHUNK_SIZE, remaining))
        if not chunk:
            break
        yield chunk
        remaining -= len(chunk)

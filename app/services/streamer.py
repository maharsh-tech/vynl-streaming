"""
Byte-range streaming proxy from Telegram.

Uses Pyrogram/wzgram download_media() which is guaranteed to exist.
Streams the file in 1 MB chunks, honoring Range headers for seek support.

ponytail: downloads sequentially from Telegram — no DC-aware multi-client pooling.
Ceiling: all stream requests share one bot's bandwidth from one DC.
Upgrade: add MULTI_TOKEN bot pool (Falix pattern) if throughput is insufficient.
"""
from __future__ import annotations

import re
from typing import AsyncGenerator

from app.services import telegram_uploader

# Pyrogram/wzgram chunks are exactly 1 MiB
CHUNK_SIZE = 1 * 1024 * 1024


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
    Optimized: skips to the exact 1MB chunk instead of downloading the whole file to RAM.
    """
    client = telegram_uploader._client  # type: ignore[assignment]
    if client is None or not client.is_connected:
        raise RuntimeError("Telegram client not connected")

    msg = await client.get_messages(chat_id, msg_id)
    if not msg or not msg.audio:
        raise ValueError(f"No audio in message {msg_id}")

    file_size: int = msg.audio.file_size
    start, end = _parse_range(range_header, file_size)

    first_chunk_index = start // CHUNK_SIZE
    skip_bytes_in_first_chunk = start % CHUNK_SIZE
    bytes_to_send = end - start + 1

    # stream_media's offset is in CHUNKS, not bytes.
    async for chunk in client.stream_media(msg, offset=first_chunk_index):
        if skip_bytes_in_first_chunk > 0:
            chunk = chunk[skip_bytes_in_first_chunk:]
            skip_bytes_in_first_chunk = 0
            
        if len(chunk) >= bytes_to_send:
            yield chunk[:bytes_to_send]
            break
            
        yield chunk
        bytes_to_send -= len(chunk)


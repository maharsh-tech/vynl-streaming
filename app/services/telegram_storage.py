from dataclasses import dataclass

from pyrogram import Client

from app.config import settings

_client: Client | None = None


@dataclass
class TelegramFileRef:
    chat_id: str
    msg_id: int
    hash: str
    file_size: int


async def start_client() -> None:
    global _client
    if _client is not None:
        return
    if not settings.telegram_configured():
        raise RuntimeError(
            "Telegram is not configured. Set API_ID, API_HASH, BOT_TOKEN, STORAGE_CHANNEL_ID in .env"
        )
    _client = Client(
        "vynl_storage",
        api_id=settings.API_ID,
        api_hash=settings.API_HASH,
        bot_token=settings.BOT_TOKEN,
        in_memory=True,
    )
    await _client.start()


async def stop_client() -> None:
    global _client
    if _client is None:
        return
    await _client.stop()
    _client = None


async def upload_audio(
    audio_path: str,
    title: str,
    filename: str,
    thumb_path: str | None = None,
) -> TelegramFileRef:
    if _client is None:
        raise RuntimeError("Telegram client is not started")

    message = await _client.send_audio(
        chat_id=settings.STORAGE_CHANNEL_ID,
        audio=audio_path,
        title=title,
        file_name=filename,
        thumb=thumb_path,
    )

    audio = message.audio
    if audio is None:
        raise RuntimeError("Telegram upload did not return audio metadata")

    chat_id = str(settings.STORAGE_CHANNEL_ID).replace("-100", "")
    return TelegramFileRef(
        chat_id=chat_id,
        msg_id=message.id,
        hash=audio.file_unique_id[:6],
        file_size=audio.file_size,
    )

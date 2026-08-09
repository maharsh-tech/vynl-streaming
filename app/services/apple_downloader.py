import asyncio
import os
import urllib.parse
from dataclasses import dataclass

import httpx

from app.exceptions import DownloadError, MultiTrackError
from app.services import aplmate_client
from app.services.aplmate_client import TIMEOUT
from app.services.download_utils import (
    clean_song_name,
    download_file,
    sanitize_filename,
    split_links,
)

_download_lock = asyncio.Semaphore(1)


@dataclass
class DownloadResult:
    audio_path: str
    thumb_path: str | None
    title: str
    filename: str
    file_size: int


async def download_track(apple_music_url: str, tmp_dir: str) -> DownloadResult:
    async with _download_lock:
        async with httpx.AsyncClient(follow_redirects=True, timeout=TIMEOUT) as client:
            await aplmate_client.init_session(client)
            token = await aplmate_client.get_token(client, apple_music_url)
            track_forms, album_thumb = await aplmate_client.get_all_track_forms(
                client, apple_music_url, token
            )

            if len(track_forms) > 1:
                raise MultiTrackError(
                    "Album/playlist URLs are not supported in Phase 2; use a single track URL"
                )
            if not track_forms:
                raise DownloadError("No tracks found for Apple Music URL")

            links = await aplmate_client.get_links_for_track(client, track_forms[0])
            audio_entry, cover_entry = split_links(links)
            if not audio_entry:
                raise DownloadError("No audio download link found")

            raw_audio_path = await download_file(
                client,
                audio_entry["link"],
                tmp_dir,
                "track.mp3",
            )

            raw_name = os.path.splitext(os.path.basename(raw_audio_path))[0]
            title = clean_song_name(urllib.parse.unquote(raw_name)) or "Unknown Track"
            filename = sanitize_filename(title)
            audio_path = os.path.join(tmp_dir, filename)
            if raw_audio_path != audio_path:
                os.rename(raw_audio_path, audio_path)

            thumb_path = None
            if cover_entry:
                cover_path = await download_file(
                    client,
                    cover_entry["link"],
                    tmp_dir,
                    "cover.jpg",
                )
                if not cover_path.lower().endswith((".jpg", ".jpeg")):
                    jpg_path = cover_path + ".jpg"
                    os.rename(cover_path, jpg_path)
                    thumb_path = jpg_path
                else:
                    thumb_path = cover_path
            elif album_thumb:
                try:
                    thumb_path = await download_file(
                        client,
                        album_thumb,
                        tmp_dir,
                        "album_thumb.jpg",
                    )
                except Exception:
                    thumb_path = None

            file_size = os.path.getsize(audio_path)
            return DownloadResult(
                audio_path=audio_path,
                thumb_path=thumb_path,
                title=title,
                filename=filename,
                file_size=file_size,
            )

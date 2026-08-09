import os
import re
import urllib.parse

import httpx

from app.services.aplmate_client import HEADERS

CHUNK_SIZE = 1 * 1024 * 1024

_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FFFF"
    "\U00002700-\U000027BF"
    "\u2600-\u26FF"
    "\u2300-\u23FF"
    "]+",
    flags=re.UNICODE,
)
_DOMAIN_PREFIX_RE = re.compile(
    r"^(?:[\w\-]+\.)+[a-zA-Z]{2,10}[\s\-\u2013\u2014]*",
    re.IGNORECASE,
)
_APLMATE_RE = re.compile(
    r"(?i)apl\s*mate\s*(?:\.com?)?\s*[-\u2013\u2014\s]*",
)


def parse_filename(response: httpx.Response, fallback: str) -> str:
    content_disposition = response.headers.get("content-disposition", "")
    match = re.search(r"filename\*=UTF-8''([^\s;]+)", content_disposition, re.IGNORECASE)
    if match:
        return urllib.parse.unquote(match.group(1))
    match = re.search(r"""filename=["']?([^"';]+)["']?""", content_disposition, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return fallback


async def download_file(
    client: httpx.AsyncClient,
    url: str,
    dest_dir: str,
    fallback_name: str,
) -> str:
    async with client.stream("GET", url, headers=HEADERS, follow_redirects=True) as response:
        response.raise_for_status()
        fname = parse_filename(response, fallback_name)
        fname = re.sub(r'[\\/*?:"<>|]', "_", fname)
        dest = os.path.join(dest_dir, fname)
        with open(dest, "wb") as handle:
            async for chunk in response.aiter_bytes(CHUNK_SIZE):
                handle.write(chunk)
    return dest


def clean_song_name(raw: str) -> str:
    name = _APLMATE_RE.sub("", raw).strip()
    for _ in range(2):
        name = _DOMAIN_PREFIX_RE.sub("", name).strip()
    name = re.sub(
        r"^[^\w\u0400-\u04FF]*Download\s+\S+\s*[-\u2013]?\s*",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    name = _EMOJI_RE.sub("", name).strip()
    name = re.sub(r"^[\s\-\u2013\u2014_•·]+", "", name).strip()
    name = re.sub(r"\s*_\s*", " ", name).strip()
    return name


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    if not cleaned.lower().endswith(".mp3"):
        cleaned += ".mp3"
    return cleaned


def split_links(links: list[dict]) -> tuple[dict | None, dict | None]:
    audio = None
    cover = None
    for item in links:
        label = item["quality"].lower()
        if "cover" in label:
            cover = item
        elif audio is None:
            audio = item
    return audio, cover

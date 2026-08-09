import asyncio
import re

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.exceptions import DownloadError

APL_BASE = "https://aplmate.com"
APL_CDN = "https://cdndl.aplmate.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": APL_BASE,
    "Referer": APL_BASE + "/",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
}

TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
RETRY_DELAY = 2.0

_SKIP_RE = re.compile(
    r"(ko-fi\.com|buymeacoffee|patreon|twitter|instagram|facebook"
    r"|youtube|tiktok|discord|t\.me|mailto:|javascript:)",
    re.IGNORECASE,
)


async def init_session(client: httpx.AsyncClient) -> None:
    await client.get(APL_BASE + "/", headers=HEADERS)


async def get_token(client: httpx.AsyncClient, music_url: str) -> str:
    response = await client.post(
        f"{APL_BASE}/action/userverify",
        data={"url": music_url},
        headers={
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    if not response.text.strip():
        raise DownloadError("aplmate userverify returned empty response")
    payload = response.json()
    if payload.get("success") and payload.get("token"):
        return payload["token"]
    raise DownloadError(f"aplmate userverify failed: {payload}")


async def get_all_track_forms(
    client: httpx.AsyncClient,
    music_url: str,
    token: str,
) -> tuple[list[dict], str | None]:
    response = await client.post(
        f"{APL_BASE}/action",
        data={"url": music_url, "cf-turnstile-response": token},
        headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
    )
    payload = response.json()
    if not payload.get("success"):
        raise DownloadError(f"aplmate /action failed: {payload.get('message')}")

    soup = BeautifulSoup(payload["html"], "html.parser")
    forms = soup.find_all("form", {"name": "submitapurl"})
    if not forms:
        raise DownloadError("No track forms found in aplmate response")

    thumb = None
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "mzstatic.com" in src or "mzcdn.com" in src:
            thumb = src
            break
    if not thumb:
        for text in soup.stripped_strings:
            match = re.search(r"https?://\S*mzstatic\.com\S+", text)
            if match:
                thumb = match.group(0).rstrip(".,)")
                break
    if not thumb:
        first_img = soup.find("img")
        if first_img:
            thumb = first_img.get("src")

    track_forms = []
    for form in forms:
        fields = {
            inp["name"]: inp["value"]
            for inp in form.find_all("input", {"type": "hidden"})
            if inp.get("name")
        }
        track_forms.append(fields)

    return track_forms, thumb


def _is_download_link(href: str) -> bool:
    if _SKIP_RE.search(href):
        return False
    if APL_CDN in href:
        return True
    if "/dl?token=" in href:
        return True
    return False


def _extract_links(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href == "#":
            continue

        full = APL_BASE + href if href.startswith("/") else href
        if full in seen:
            continue
        seen.add(full)

        if not _is_download_link(full):
            continue

        label = anchor.get_text(strip=True) or "Download"
        if re.search(r"another\s+song", label, re.IGNORECASE):
            continue

        results.append({"quality": label, "link": full})

    return results


async def get_links_for_track(
    client: httpx.AsyncClient,
    fields: dict,
    track_index: int = 1,
) -> list[dict]:
    max_retries = settings.APL_MAX_RETRIES
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.post(
                f"{APL_BASE}/action/track",
                data=fields,
                headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
            )
            payload = response.json()

            if payload.get("error"):
                message = payload.get("message", "")
                if attempt < max_retries and re.search(
                    r"refresh|try again|session", message, re.IGNORECASE
                ):
                    await asyncio.sleep(RETRY_DELAY * attempt)
                    continue
                raise DownloadError(f"aplmate track error: {message}")

            raw_html = payload.get("data") or payload.get("html") or ""
            results = _extract_links(raw_html)
            if not results:
                raise DownloadError("No download links found in aplmate track response")
            return results

        except httpx.TimeoutException as exc:
            if attempt < max_retries:
                await asyncio.sleep(RETRY_DELAY * (2 ** (attempt - 1)))
                continue
            raise DownloadError(f"aplmate track request timed out: {exc}") from exc

    raise DownloadError("aplmate track request failed after retries")

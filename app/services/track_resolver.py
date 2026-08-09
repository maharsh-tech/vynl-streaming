import httpx

from app.config import settings
from app.exceptions import TrackNotFoundError
from app.models.track import ResolveResponse, SearchCandidate

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def _build_query(title: str, artist: str | None) -> str:
    title = title.strip()
    if artist:
        return f"{artist.strip()} {title}"
    return title


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _artwork_url(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.replace("100x100bb", "600x600bb")


def _candidate_from_result(item: dict) -> SearchCandidate | None:
    track_id = item.get("trackId")
    url = item.get("trackViewUrl")
    title = item.get("trackName")
    artist = item.get("artistName")

    if not all([track_id, url, title, artist]):
        return None

    return SearchCandidate(
        title=title,
        artist=artist,
        apple_track_id=int(track_id),
        apple_music_url=url,
        duration_ms=item.get("trackTimeMillis"),
        artwork_url=_artwork_url(item.get("artworkUrl100")),
    )


def _score_candidate(
    candidate: SearchCandidate,
    title: str,
    artist: str | None,
) -> tuple[int, int]:
    title_match = _normalize(candidate.title) == _normalize(title)
    artist_match = (
        _normalize(candidate.artist) == _normalize(artist)
        if artist
        else False
    )
    return (int(title_match), int(artist_match))


async def _fetch_candidates(title: str, artist: str | None) -> list[SearchCandidate]:
    params = {
        "term": _build_query(title, artist),
        "entity": "song",
        "limit": settings.ITUNES_SEARCH_LIMIT,
        "country": settings.ITUNES_SEARCH_COUNTRY,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(ITUNES_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = response.json()

    results = payload.get("results", [])
    candidates: list[SearchCandidate] = []

    for item in results:
        candidate = _candidate_from_result(item)
        if candidate:
            candidates.append(candidate)

    return candidates


async def search_tracks(title: str, artist: str | None = None) -> list[SearchCandidate]:
    return await _fetch_candidates(title, artist)


async def resolve_track(title: str, artist: str | None = None) -> ResolveResponse:
    candidates = await _fetch_candidates(title, artist)
    if not candidates:
        raise TrackNotFoundError(f"No Apple Music match for: {_build_query(title, artist)}")

    best = max(
        candidates,
        key=lambda candidate: _score_candidate(candidate, title, artist),
    )

    return ResolveResponse(
        title=best.title,
        artist=best.artist,
        apple_track_id=best.apple_track_id,
        apple_music_url=best.apple_music_url,
        duration_ms=best.duration_ms,
        artwork_url=best.artwork_url,
    )

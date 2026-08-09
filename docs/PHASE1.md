# Phase 1 — Implementation Plan

**Scope:** Song name → **Apple Music link**. Nothing else yet.

**Goal:** Calling backend service sends `{ title, artist }` and gets back `apple_music_url`.

**Not in Phase 1:** MP3 download, Telegram, MongoDB, ingest, streaming.

Reference: [PLAN.md](../PLAN.md)

---

## Current state

Already done:

- [x] Project scaffold (`app/`, packages, `/health`)
- [x] `.env.example`, `requirements.txt`, `.gitignore`
- [x] Architecture plan

---

## Phase 1 deliverables

| # | Deliverable | Done when |
|---|-------------|-----------|
| 1 | Config for resolver settings | `ITUNES_SEARCH_COUNTRY` loads from env |
| 2 | Track resolver service | iTunes Search → best match |
| 3 | Resolve API route | `POST /api/v1/tracks/resolve` works |
| 4 | Optional search route | `GET /api/v1/tracks/search` returns candidates |

---

## Suggested commit order

```
1. docs: narrow phase 1 scope to apple music link resolution
2. chore: add resolver config and httpx dependency
3. feat: add resolve response pydantic models
4. feat: add itunes track resolver service
5. feat: add tracks resolve api route
6. feat: add optional search preview route
7. docs: update readme with resolve endpoint examples
```

Push after each commit.

---

## Step 1 — Config

**Commit:** `chore: add resolver config and httpx dependency`

**File:** `app/config.py`

| Variable | Required | Default |
|----------|----------|---------|
| `PORT` | no | `8000` |
| `ITUNES_SEARCH_COUNTRY` | no | `US` |

No Telegram, MongoDB, or API keys needed for Phase 1.

**File:** `requirements.txt` — add:

```
httpx
```

---

## Step 2 — Models

**Commit:** `feat: add resolve response pydantic models`

**File:** `app/models/track.py`

```python
class ResolveRequest(BaseModel):
    title: str
    artist: str | None = None

class ResolveResponse(BaseModel):
    title: str
    artist: str
    apple_track_id: int
    apple_music_url: str
    duration_ms: int | None = None
    artwork_url: str | None = None

class SearchCandidate(BaseModel):
    title: str
    artist: str
    apple_track_id: int
    apple_music_url: str
    duration_ms: int | None = None
    artwork_url: str | None = None
```

---

## Step 3 — iTunes resolver service

**Commit:** `feat: add itunes track resolver service`

**File:** `app/services/track_resolver.py`

### iTunes Search API

```
GET https://itunes.apple.com/search
  ?term={query}
  &entity=song
  &limit=5
  &country={ITUNES_SEARCH_COUNTRY}
```

No API key required.

### Public interface

```python
async def search_tracks(title: str, artist: str | None = None) -> list[SearchCandidate]:
    """Return up to 5 matches from iTunes."""

async def resolve_track(title: str, artist: str | None = None) -> ResolveResponse:
    """Pick best match and return Apple Music link."""
```

### Query building

```python
query = f"{artist} {title}".strip() if artist else title
```

### Scoring (pick best match)

1. Exact title match (case-insensitive)
2. Exact artist match if artist was provided
3. Fallback: first result

### Apple Music URL

Use `trackViewUrl` from iTunes response, or build:

```
https://music.apple.com/song/id{trackId}
```

### Errors

| Exception | When |
|-----------|------|
| `TrackNotFoundError` | Zero iTunes results |

---

## Step 4 — Resolve API route

**Commit:** `feat: add tracks resolve api route`

**File:** `app/api/tracks.py`

```python
@router.post("/tracks/resolve", response_model=ResolveResponse)
async def resolve_track(body: ResolveRequest):
    ...
```

**File:** `app/main.py` — register router:

```python
app.include_router(tracks_router, prefix="/api/v1")
```

### Response codes

| Code | When |
|------|------|
| 200 | Match found |
| 400 | Missing/empty `title` |
| 404 | No results on Apple Music / iTunes |

---

## Step 5 — Optional search preview

**Commit:** `feat: add optional search preview route`

**File:** `app/api/tracks.py`

```python
@router.get("/tracks/search", response_model=list[SearchCandidate])
async def search_tracks(title: str, artist: str | None = None):
    ...
```

Useful when the calling service wants to show candidates before committing to one match.

---

## Step 6 — README

**Commit:** `docs: update readme with resolve endpoint examples`

Add curl examples and note that download/storage comes in Phase 2+.

---

## API contract

### POST `/api/v1/tracks/resolve`

**Request:**

```json
{
  "title": "Blinding Lights",
  "artist": "The Weeknd"
}
```

**Response 200:**

```json
{
  "title": "Blinding Lights",
  "artist": "The Weeknd",
  "apple_track_id": 1499378106,
  "apple_music_url": "https://music.apple.com/us/album/blinding-lights/...",
  "duration_ms": 200040,
  "artwork_url": "https://is1-ssl.mzstatic.com/image/thumb/..."
}
```

### GET `/api/v1/tracks/search?title=...&artist=...`

**Response 200:**

```json
[
  {
    "title": "Blinding Lights",
    "artist": "The Weeknd",
    "apple_track_id": 1499378106,
    "apple_music_url": "https://music.apple.com/...",
    "duration_ms": 200040,
    "artwork_url": "https://..."
  }
]
```

---

## Manual test checklist

- [ ] `/health` returns `{ "status": "ok" }`
- [ ] Resolve known song + artist → valid `apple_music_url`
- [ ] `apple_music_url` opens correct track on Apple Music
- [ ] Resolve nonsense query → `404`
- [ ] Resolve title-only → returns best guess (log artist for verification)
- [ ] Search endpoint returns multiple candidates

**Example curls:**

```bash
curl -X POST http://localhost:8000/api/v1/tracks/resolve \
  -H "Content-Type: application/json" \
  -d '{"title":"Blinding Lights","artist":"The Weeknd"}'

curl "http://localhost:8000/api/v1/tracks/search?title=Blinding%20Lights&artist=The%20Weeknd"
```

---

## File map after Phase 1

```
app/
├── main.py                      # router + /health
├── config.py                    # ITUNES_SEARCH_COUNTRY, PORT
├── api/
│   └── tracks.py                # resolve + search
├── services/
│   └── track_resolver.py        # iTunes search logic
└── models/
    └── track.py                 # request/response models
```

**Not created until Phase 2+:**

- `app/services/apple_downloader.py`
- `app/services/telegram_storage.py`
- `app/db/`

---

## Definition of done

Phase 1 is complete when:

1. All commits above are pushed to `main`
2. Manual test checklist passes
3. Calling service can get a working `apple_music_url` from a song name

---

## What comes next

| Phase | Work |
|-------|------|
| **Phase 2** | Download MP3 — file download route for testing (not stream URLs) |
| **Phase 3** | Telegram storage + `POST /ingest` + MongoDB |
| **Phase 4** | Temp stream URLs from Telegram + byte-range streaming |
| **Phase 5** | API keys, rate limits, Docker |

Do not start Phase 2 until resolve is stable and tested.

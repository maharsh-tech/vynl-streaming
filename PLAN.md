# VYNL Audio Streaming Microservice — Plan

**Pure backend service.** No frontend, no user UI, no public Telegram bot. Only other backend services call this API.

> **Current build target (Phase 2):** Download `.mp3` for testing only. Stream URLs from Telegram come in Phase 4. See [docs/PHASE2.md](./docs/PHASE2.md).

Plan for `vynl-audio-streaming`, built from two reference codebases:

| Source | Role |
|--------|------|
| `D:\Projects\Apple-Music-Bot-main` | Download `.mp3` from Apple Music (via aplmate.com) |
| `D:\FalixMovies FULLSTACK\falix-backend-main` | Telegram private-channel storage + byte-range streaming |

---

## 1. What We're Building

A **backend-only** microservice (FastAPI) that other services talk to over HTTP.

**Full vision (all phases):**

1. **Resolve** — calling service sends **song name** (+ optional artist) → we return an **Apple Music link**
2. **Download** — fetch `.mp3` from Apple Music (via aplmate.com)
3. **Store** in a private Telegram channel (Falix-style)
4. **Return temp stream URLs** (1–2 hr TTL) for playback
5. **Regenerate** links when they expire

**Phase 1 stops at step 1** — we only resolve and return the Apple Music URL.

### Who interacts with what

| Actor | Interaction |
|-------|-------------|
| **Calling backend service** | `POST /ingest`, `GET /stream-link` (API key) |
| **Calling service's player** | `GET /stream/{token}/{name}.mp3` (direct HTTP, supports Range/seek) |
| **End user** | Never touches VYNL directly — only through the calling service |
| **Telegram** | Internal storage only — not a user-facing bot |

### Typical calling-service flow (full product)

```
1. User picks a song in YOUR app
2. YOUR backend → POST vynl /api/v1/tracks/resolve { title, artist }     ← Phase 1
3. VYNL returns { apple_music_url, apple_track_id, title, artist }
4. YOUR backend → POST vynl /api/v1/tracks/ingest { ... }                ← Phase 3
5. VYNL downloads, stores in Telegram → { track_id }
6. YOUR backend → GET vynl /api/v1/tracks/{track_id}/stream-link         ← Phase 4
7. VYNL returns { stream_url, expires_at }
8. YOUR player plays stream_url directly
9. Link expires → request new stream-link (step 6)
```

### Phase 1 flow (what we build now)

```
YOUR backend → POST /api/v1/tracks/resolve { "title": "...", "artist": "..." }
VYNL         → iTunes Search API → pick best match
VYNL         → { "apple_music_url": "https://music.apple.com/...", ... }
```

---

## 2. High-Level Architecture

### Phase 1 (current)

```mermaid
flowchart LR
    CB[Calling Backend Service]
    API[FastAPI]
    RES[iTunes Track Resolver]
    IT[iTunes Search API]

    CB -->|"POST /resolve {title, artist}"| API
    API --> RES --> IT
    RES -->|apple_music_url| API
    API --> CB
```

### Full system (later phases)

```mermaid
flowchart LR
    subgraph CallingService["Calling Backend Service"]
        CB[Your API]
        PL[Your Audio Player]
    end

    subgraph VYNL["vynl-audio-streaming"]
        API[FastAPI REST API]
        RES[Track Resolver]
        DL[Apple Music Downloader]
        TG[Telegram Uploader]
        STR[Byte Streamer]
        DB[(MongoDB)]
    end

    subgraph Internal["Internal only"]
        CH[Private Telegram Channel]
    end

    CB -->|"POST /resolve"| API
    CB -->|"POST /ingest"| API
    CB -->|"GET /stream-link"| API
    API --> RES
    API --> DL --> TG --> CH
    TG --> DB
    CB -->|stream_url| PL
    PL --> STR --> CH
```

---

## 3. What We Reuse From Each Repo

### From Apple Music Bot (`ap.py` + download helpers)

| Piece | Purpose |
|-------|---------|
| `init_session()` | Session with aplmate.com |
| `get_token()` | Turnstile/userverify token |
| `get_all_track_forms()` | Parse album/playlist/track |
| `get_links_for_track()` | Resolve CDN MP3 URL |
| `download_file()` | Stream download to disk |
| `clean_song_name()` | Normalize title/filename |

**Flow:** Apple Music URL → aplmate token → track forms → CDN link → local `.mp3` (+ optional cover art).

### From Falix Backend

| Piece | Purpose |
|-------|---------|
| `ByteStreamer` | Range-aware streaming from Telegram DC |
| `encode_string` / `decode_string` | Encode `{chat_id, msg_id, hash}` |
| Pyrogram multi-client setup | Load balancing across bot tokens |
| Channel listener pattern | Detect uploads in `AUTH_CHANNEL` |

**Falix gap:** `/dl/{id}/{name}` links are **permanent**. We add a **token layer with TTL** on top.

**Apple Music Bot gap:** Ingestion only accepts `music.apple.com` URLs today. We add a **track resolver** so callers can pass a song name instead.

---

## 4. Song Name → Apple Music URL (Resolver)

The downloader (`ap.py`) needs an Apple Music link. Callers will send a **song name**, not a URL. We resolve it first.

### Recommended: iTunes Search API (free, no API key)

```
GET https://itunes.apple.com/search
  ?term={artist}+{song_title}
  &entity=song
  &limit=5
  &country=US
```

Returns JSON with `trackViewUrl`, `trackName`, `artistName`, `trackId`, `trackTimeMillis`, `artworkUrl100`.

Example response field:

```json
{
  "trackName": "Blinding Lights",
  "artistName": "The Weeknd",
  "trackViewUrl": "https://music.apple.com/us/album/...",
  "trackId": 1499378106
}
```

That `trackViewUrl` (or a constructed `https://music.apple.com/song/id{trackId}`) feeds directly into the existing `ap.py` pipeline.

### Matching strategy

| Input | Behavior |
|-------|----------|
| `{ "title": "Blinding Lights", "artist": "The Weeknd" }` | Search `The Weeknd Blinding Lights`, pick best match |
| `{ "title": "Blinding Lights" }` | Search title only; may be ambiguous |
| `{ "query": "Blinding Lights The Weeknd" }` | Single free-text string |

**Scoring (pick best result):**

1. Exact title match (case-insensitive)
2. Exact artist match if artist was provided
3. Prefer shorter duration delta if metadata available
4. Fallback: first result

### Ambiguity handling

If multiple close matches exist, two options:

- **Auto mode (default):** pick top scored match, return it in response so caller can verify
- **Strict mode:** return `409` with `candidates[]` and require a second call with `apple_track_id` or `trackViewUrl`

### Dedup key

Use `trackId` from iTunes (same as Apple Music catalog ID) as `apple_track_id` for dedup — not the raw song name string.

### Optional: direct URL still supported

Keep URL ingest as a fallback for playlists/albums or when the caller already has the link:

```json
{ "url": "https://music.apple.com/..." }
```

---

## 5. Core Flows

### Flow A — Resolve Apple Music link *(Phase 1 — build now)*

```
POST /api/v1/tracks/resolve
Body: { "title": "Blinding Lights", "artist": "The Weeknd" }
```

1. Build search query from `title` + optional `artist`
2. Call iTunes Search API → get matches
3. Score and pick best match
4. Return:

```json
{
  "title": "Blinding Lights",
  "artist": "The Weeknd",
  "apple_track_id": 1499378106,
  "apple_music_url": "https://music.apple.com/...",
  "duration_ms": 200040,
  "artwork_url": "https://..."
}
```

**Phase 1 stops here.**

### Flow B — Ingest (search + download + store) *(Phase 3)*

```
POST /api/v1/tracks/ingest
Body: { "title": "Blinding Lights", "artist": "The Weeknd" }
```

1. Run Flow A → get `apple_music_url`
2. Check dedup by `apple_track_id` — if exists, return existing `track_id`
3. Run `ap.py` flow with resolved URL → download MP3 to temp dir
4. Upload to private channel via Pyrogram `send_audio()`
5. Capture `chat_id`, `msg_id`, `file_unique_id[:6]` (hash)
6. Save track record in MongoDB
7. Return:

```json
{
  "track_id": "uuid",
  "title": "Blinding Lights",
  "artist": "The Weeknd",
  "apple_track_id": 1499378106,
  "apple_music_url": "https://music.apple.com/...",
  "status": "stored"
}
```

**Dedup:** Same `apple_track_id` → skip re-download, return existing `track_id` (even if song name spelling differed).

### Flow C — Issue temp stream link *(Phase 4)*

```
GET /api/v1/tracks/{track_id}/stream-link
Header: X-API-Key: <service-key>
Query: ttl=7200  (optional, default 1–2 hr)
```

1. Authenticate calling service (API key)
2. Look up track → get Telegram refs
3. Generate random token (e.g. `secrets.token_urlsafe(32)`)
4. Store in DB/Redis: `{ token, track_id, expires_at, created_at }`
5. Return:

```json
{
  "stream_url": "https://vynl.example.com/stream/{token}/song-name.mp3",
  "expires_at": "2026-08-09T20:14:00Z",
  "ttl_seconds": 7200
}
```

### Flow D — Stream (play audio) *(Phase 4)*

```
GET /stream/{token}/{filename}.mp3
Header: Range: bytes=0-  (optional)
```

1. Look up token → reject **410 Gone** if expired/missing
2. Resolve track → decode `{chat_id, msg_id, hash}`
3. Verify hash matches file (same as Falix)
4. Stream via `ByteStreamer` with `Content-Type: audio/mpeg`, `Accept-Ranges: bytes`, **206** for range requests
5. Do **not** delete the Telegram file — only the token expires

### Flow E — Regenerate link *(Phase 4)*

Same as Flow B. Calling service hits `/stream-link` again → new token, new expiry. Old tokens remain invalid after expiry (background cleanup optional).

---

## 6. Suggested Project Structure

```
vynl-audio-streaming/
├── app/
│   ├── main.py                 # FastAPI entry
│   ├── config.py               # env vars
│   ├── api/
│   │   ├── tracks.py           # ingest, stream-link, track info
│   │   └── stream.py           # GET /stream/{token}/{name}
│   ├── services/
│   │   ├── track_resolver.py   # song name → Apple Music URL (iTunes Search)
│   │   ├── apple_downloader.py # ported from ap.py + apple.py
│   │   ├── telegram_storage.py # upload to channel
│   │   ├── token_service.py    # create/validate/expiry
│   │   └── streamer.py         # ByteStreamer wrapper
│   ├── models/
│   │   ├── track.py
│   │   └── stream_token.py
│   └── db/
│       └── mongodb.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

## 7. Database Schema (MongoDB)

### `tracks` collection

```json
{
  "_id": "ObjectId",
  "track_id": "uuid-or-cuid",
  "search_query": "Blinding Lights The Weeknd",
  "resolved_url": "https://music.apple.com/...",
  "apple_track_id": "1234567890",
  "title": "Song Name",
  "artist": "Artist Name",
  "filename": "Song Name.mp3",
  "file_size": 5242880,
  "duration_sec": 210,
  "thumbnail_url": "...",
  "telegram": {
    "chat_id": "1234567890",
    "msg_id": 42,
    "hash": "abc123",
    "encoded_id": "base62-compressed-id"
  },
  "status": "stored | failed | processing",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

Indexes: `track_id` (unique), `apple_track_id` (unique), `status`

### `stream_tokens` collection

```json
{
  "token": "random-url-safe-string",
  "track_id": "uuid",
  "expires_at": "ISO8601",
  "created_at": "ISO8601",
  "requested_by": "service-name-or-api-key-id"
}
```

Indexes: `token` (unique), TTL index on `expires_at` (auto-delete expired tokens)

**Optional:** Redis instead of Mongo TTL for hot token lookups.

---

## 8. API Surface (backend-to-backend only)

### Phase 1 endpoints *(done)*

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/tracks/resolve` | none (Phase 5) | Song name → Apple Music link |
| `GET` | `/api/v1/tracks/search` | none (Phase 5) | Preview iTunes matches (optional) |
| `GET` | `/health` | none | Health check |

### Phase 2 endpoints *(current — MP3 file download for testing)*

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tracks/download` | Resolve + download MP3, return file metadata |
| `GET` | `/api/v1/tracks/download/file/{token}` | Return `.mp3` file (temporary test route) |

**Important:** Phase 2 `download_url` is a **file download link**, not the final stream URL. Final temp stream URLs (`/stream/{token}/{name}`) are generated from **Telegram-stored files** in Phase 4.

**Download response (Phase 2):**

```json
{
  "title": "Blinding Lights",
  "filename": "Blinding Lights.mp3",
  "file_size": 5242880,
  "apple_music_url": "https://music.apple.com/...",
  "download_url": "/api/v1/tracks/download/file/abc123",
  "expires_at": "2026-08-09T19:00:00Z"
}
```

### Later phases

| Method | Endpoint | Phase | Description |
|--------|----------|-------|-------------|
| `POST` | `/api/v1/tracks/ingest` | 3 | Resolve + download + store in Telegram |
| `GET` | `/api/v1/tracks/{track_id}` | 3 | Stored track metadata |
| `GET` | `/api/v1/tracks/{track_id}/stream-link` | 4 | Issue temp stream URL from Telegram file |
| `GET` | `/stream/{token}/{name}` | 4 | Stream MP3 from Telegram (Range/seek) |

API key auth (`X-API-Key`) added in Phase 5.

---

## 9. Environment Variables

```env
# Telegram
API_ID=
API_HASH=
BOT_TOKEN=
STORAGE_CHANNEL_ID=-100xxxxxxxxxx    # private channel
MULTI_TOKEN1=                        # optional extra bots for streaming load

# Database
MONGO_URI=
MONGO_DB=vynl_audio

# Track resolution
ITUNES_SEARCH_COUNTRY=US             # region for Apple Music catalog matching

# Server
BASE_URL=https://vynl.yourdomain.com
PORT=8000
STREAM_TOKEN_TTL=7200                # seconds (1-2 hr)

# Security
API_KEYS=key1,key2                   # calling services
SECRET_KEY=                          # if signing tokens with JWT instead
```

---

## 10. Implementation Phases

### Phase 1 — Resolve Apple Music link *(done)*

- [x] Project scaffold + `/health`
- [x] Config (`ITUNES_SEARCH_COUNTRY`, server settings)
- [x] `track_resolver.py` — iTunes Search API (song name → Apple Music URL)
- [x] `POST /api/v1/tracks/resolve` — return link + metadata
- [x] `GET /api/v1/tracks/search` — preview candidates

Details: [docs/PHASE1.md](./docs/PHASE1.md)

### Phase 2 — Download MP3 *(current — testing only)*

- [ ] Port `ap.py` downloader into `apple_downloader.py`
- [ ] Apple Music URL → local `.mp3` (single track)
- [ ] `POST /api/v1/tracks/download` — trigger download, return metadata
- [ ] `GET /api/v1/tracks/download/file/{token}` — return `.mp3` file for testing

**Phase 2 gives a file download, NOT a stream link.** This is temporary so we can verify aplmate download works before Telegram storage.

**Not in Phase 2:** Telegram, MongoDB, temp stream URLs, byte-range streaming.

Details: [docs/PHASE2.md](./docs/PHASE2.md)

### Phase 3 — Store in Telegram + ingest

- [ ] MongoDB + `tracks` collection
- [ ] Telegram upload to private channel
- [ ] `POST /api/v1/tracks/ingest` — resolve + download + store
- [ ] Dedup by `apple_track_id`

### Phase 4 — Temp stream links *(from Telegram storage)*

- [ ] Port Falix `ByteStreamer` + Pyrogram multi-client
- [ ] Token service + TTL (1–2 hr self-destruct)
- [ ] `GET /api/v1/tracks/{id}/stream-link` — issue playable URL
- [ ] `GET /stream/{token}/{name}` — stream MP3 from Telegram with Range support

**This is where the real stream URLs come from** — generated from files stored in the private Telegram channel, not from local disk.

### Phase 5 — Production hardening

- [ ] API key auth middleware
- [ ] Rate limiting
- [ ] Logging + error handling (FloodWait, aplmate failures)
- [ ] Docker + deploy config

---

## 11. Key Design Decisions

| Decision | Recommendation | Why |
|----------|----------------|-----|
| Service type | **Backend-only** REST API | Callers are other services, not end users |
| Playback | Caller uses `stream_url` in their player | VYNL does not serve UI or embed players |
| Ingest input | Song `title` + optional `artist` | Matches how calling services know tracks |
| Name → URL | iTunes Search API | Free, no key, returns Apple Music URLs |
| Temp link mechanism | Opaque token in DB with TTL | Simpler than JWT; easy revoke; Falix IDs stay internal |
| Default TTL | **2 hours** (configurable) | Matches requirement |
| Storage format | `send_audio()` in Telegram | Native audio metadata; players handle it well |
| Stream protocol | HTTP byte-range (206) | Required for seeking in audio players |
| Auth for ingest/link | API key per calling service | Simple service-to-service auth |
| Dedup key | `apple_track_id` from iTunes | Same song under different spellings won't re-download |

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Wrong song picked (ambiguous name) | Require `artist` when possible; optional `/search` preview; return resolved title/artist in response |
| Song not on Apple Music | Return `404` with clear message; optional fallback search providers later |
| aplmate.com downtime / rate limits | Retry logic (already in `ap.py`), semaphore limits, cache stored tracks |
| Telegram FloodWait on upload | Delays between uploads, queue |
| Permanent Falix links vs temp links | Never expose encoded Telegram ID publicly; only expose short-lived tokens |
| Large files / slow stream | Multi-client ByteStreamer (Falix pattern), chunk cache |
| Legal / ToS | Document that this is for your own licensed/private use |

---

## 13. What We Are NOT Building (Scope Boundary)

- No frontend / web UI / mobile app
- No embedded audio player page
- No public Telegram bot for users (Telegram is storage-only, internal)
- No user auth/login — only API keys between backend services
- No TMDB/movie catalog (Falix-specific, not needed here)
- No permanent public download URLs

---

## 14. Success Criteria

### Phase 1 (current)

1. Calling service sends `{ title, artist }` → gets valid `apple_music_url`
2. Wrong/unknown song → clear `404`
3. Response includes resolved `title`, `artist`, `apple_track_id` so caller can verify match

### Full product (all phases)

1. Resolve → download → store in Telegram
2. Calling service gets temp `stream_url` → plays with seek
3. Link expires → new link on request
4. End users never touch VYNL directly

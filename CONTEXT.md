# Project Context — vynl-audio-streaming

Handoff doc for the next agent. Read this before making changes.

---

## What this project is

**Pure backend microservice** (FastAPI). Other backend services call it over HTTP — no frontend, no user-facing Telegram bot.

**End goal:** Calling service sends a song name → we resolve, download, store in a **private Telegram channel**, then issue **temp stream URLs** (1–2 hr TTL) that play audio from Telegram (Falix-style).

**Repo:** https://github.com/maharsh-tech/vynl-streaming  
**Branch:** `main`  
**Local path:** `d:\Projects\vynl-audio-streaming`

---

## Reference codebases (do not copy blindly — port what’s needed)

| Repo | Use for |
|------|---------|
| `D:\Projects\Apple-Music-Bot-main` | Download MP3 via **aplmate.com** (`ap.py`, download helpers in `apple.py`) |
| `D:\FalixMovies FULLSTACK\falix-backend-main` | Telegram storage + **ByteStreamer** temp links (Phase 3–4, not started) |

Wrong repo was initially referenced (IMMS) — ignore it. Use **Falix** for Telegram/streaming.

---

## Build workflow (important)

User wants **human-like incremental work**:

- Small, focused commits with clear messages
- Push to `main` regularly after each logical unit
- Do **not** implement everything at once
- Follow phase plans in `docs/PHASE1.md`, `docs/PHASE2.md`, and `PLAN.md`

---

## Phase status

| Phase | Status | What it does |
|-------|--------|--------------|
| **1** | Done | Song name → Apple Music URL (iTunes Search API) |
| **2** | Done | Apple Music URL → download MP3 → **return file directly** (testing) |
| **3** | Not started | Upload to Telegram + MongoDB + `POST /ingest` |
| **4** | Not started | Temp stream URLs from Telegram + byte-range `/stream/{token}` |
| **5** | Not started | API keys, rate limits, Docker |

---

## Critical product decisions (do not regress)

1. **Ingest input is song name** (+ optional artist), not raw URL — resolved via iTunes Search first.
2. **Phase 2 is download testing only** — returns `.mp3` file on `POST /tracks/download`. No Telegram in Phase 2.
3. **Temp stream URLs come from Telegram** in Phase 4 — not from local disk, not from a token cache.
4. **User explicitly rejected** Telegram upload in Phase 2 (commit `f14327e` reverted a brief Telegram experiment).
5. **No frontend** — calling backend hits REST API; player uses stream URL later.
6. **Single track only** in Phase 2 — album/playlist URLs return `422` (`MultiTrackError`).

---

## What is implemented now

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/tracks/resolve` | `{ title, artist? }` → Apple Music metadata + URL |
| `GET` | `/api/v1/tracks/search` | Preview iTunes matches |
| `POST` | `/api/v1/tracks/download` | Resolve + download → **returns MP3 file** (`FileResponse`) |

### Services

| File | Role |
|------|------|
| `app/services/track_resolver.py` | iTunes Search API → best match |
| `app/services/aplmate_client.py` | Port of `ap.py` — aplmate session, token, track links |
| `app/services/download_utils.py` | Port of `apple.py` helpers — CDN download, filename cleaning |
| `app/services/apple_downloader.py` | Orchestrates single-track download |

### Models & config

- `app/models/track.py` — `ResolveRequest/Response`, `SearchCandidate`, `DownloadRequest`
- `app/config.py` — `ITUNES_SEARCH_COUNTRY`, `DOWNLOAD_TIMEOUT` (120s), `APL_MAX_RETRIES`
- No MongoDB, no Pyrogram, no Telegram env vars in current code

### Removed / do not re-add without user ask

- `app/services/download_cache.py` — token-based local file URLs (removed; user wants direct file + Telegram streams later)
- `app/services/telegram_storage.py` — briefly added, reverted in `f14327e`
- `GET /tracks/download/file/{token}` — removed

---

## Project structure

```
vynl-audio-streaming/
├── PLAN.md                 # Full architecture + all phases
├── CONTEXT.md              # This file
├── README.md               # Setup + test commands
├── docs/
│   ├── PHASE1.md           # Phase 1 implementation plan (done)
│   └── PHASE2.md           # Phase 2 plan (done, direct file return)
├── app/
│   ├── main.py
│   ├── config.py
│   ├── exceptions.py
│   ├── api/tracks.py
│   ├── models/track.py
│   └── services/
│       ├── track_resolver.py
│       ├── aplmate_client.py
│       ├── download_utils.py
│       └── apple_downloader.py
├── requirements.txt
└── .env.example
```

---

## How download works (Phase 2)

```
POST /api/v1/tracks/download
  → (optional) track_resolver.resolve_track()
  → apple_downloader.download_track(apple_music_url)
       → aplmate: init_session → get_token → get_all_track_forms → get_links_for_track
       → download_utils.download_file from CDN
  → FileResponse with .mp3 (temp dir cleaned up after send)
```

**Expect 10–30 seconds** (sometimes up to ~2 min). Swagger looks “stuck” while waiting — normal.

**Concurrency:** `_download_lock = asyncio.Semaphore(1)` in `apple_downloader.py` — only one download at a time.

---

## Environment variables (current)

```env
PORT=8000
BASE_URL=http://localhost:8000
ITUNES_SEARCH_COUNTRY=US
ITUNES_SEARCH_LIMIT=5
APL_MAX_RETRIES=3
DOWNLOAD_TIMEOUT=120
```

Telegram vars will be needed in **Phase 3** — not configured yet.

---

## Testing (Windows PowerShell)

`curl` is aliased to `Invoke-WebRequest` — use `Invoke-RestMethod` or `curl.exe`.

```powershell
# Resolve
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/tracks/resolve" `
  -ContentType "application/json" `
  -Body '{"title":"Blinding Lights","artist":"The Weeknd"}'

# Download (saves file)
Invoke-WebRequest -Method POST -Uri "http://localhost:8000/api/v1/tracks/download" `
  -ContentType "application/json" `
  -Body '{"title":"Daylight","artist":"David Kushner"}' `
  -OutFile "daylight.mp3"
```

Swagger: http://localhost:8000/docs

---

## Known issues / notes

- **aplmate.com** is external and can be slow or flaky — retries exist in `aplmate_client.py`.
- **tgcrypto** failed to build on Windows (needs MSVC) — irrelevant until Phase 3 Pyrogram.
- Filenames from CDN may contain URL-encoded chars — `urllib.parse.unquote` applied in `apple_downloader.py`.
- User on Windows — prefer PowerShell examples in docs.

---

## Git history (high level)

```
f14327e revert: remove telegram from phase 2, return mp3 file directly   ← CURRENT
0556894 refactor: download uploads to telegram... (reverted by above)
... Phase 2 download commits (aplmate, apple_downloader, etc.)
0057bc8 docs: update readme with resolve endpoint examples
... Phase 1 commits (track_resolver, resolve/search routes)
521d80a chore: scaffold initial project structure
67be8cc Initial commit
```

---

## What to build next (Phase 3)

When user asks to continue:

1. Add Pyrogram + Telegram upload to private channel (`send_audio`)
2. MongoDB `tracks` collection — store `{ chat_id, msg_id, hash }` + metadata
3. `POST /api/v1/tracks/ingest` — resolve + download + upload + dedup by `apple_track_id`
4. Do **not** add temp stream URLs yet — that's Phase 4 (Falix `ByteStreamer` + token TTL)

See `PLAN.md` sections 10–11 and Phase 3 checklist.

---

## Docs map

| File | Purpose |
|------|---------|
| [PLAN.md](./PLAN.md) | Master architecture, all phases, API surface |
| [docs/PHASE1.md](./docs/PHASE1.md) | Phase 1 details (complete) |
| [docs/PHASE2.md](./docs/PHASE2.md) | Phase 2 details (complete) |
| [CONTEXT.md](./CONTEXT.md) | This handoff summary |

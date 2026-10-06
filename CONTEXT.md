# Project Context — vynl-audio-streaming

Handoff doc for the next agent. Read this before making changes.

---

## What this project is

**Pure backend microservice** (FastAPI). Other backend services call it over HTTP — no frontend, no user-facing Telegram bot.

**End goal (Completed):** Calling service sends a song name → we resolve, download, store in a **private Telegram channel**, then issue **temp stream URLs** (1–2 hr TTL) that proxy bytes directly from Telegram via an optimized `ByteStreamer`.

**Repo:** https://github.com/maharsh-tech/vynl-streaming  
**Branch:** `main`  
**Local path:** `d:\Projects\vynl-audio-streaming`

---

## Phase status

| Phase | Status | What it does |
|-------|--------|--------------|
| **1** | Done | Song name → Apple Music URL (iTunes Search API) |
| **2** | Dropped | Legacy direct download testing (removed) |
| **3** | Done | Upload to Telegram + MongoDB + `POST /ingest` |
| **4** | Done | Temp stream URLs + optimized `ByteStreamer` range proxy |
| **5** | Not started | API keys, rate limits, Docker (optional future) |

---

## What is implemented now

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (verifies Mongo & Telegram connection) |
| `GET` | `/api/v1/tracks/search` | Search iTunes for candidates |
| `POST` | `/api/v1/tracks/resolve` | Select candidate, resolve metadata |
| `POST` | `/api/v1/tracks/ingest` | Dedup/Download/Upload/Save to DB |
| `GET` | `/api/v1/tracks/{track_id}/stream-link` | Generate 2-hour expiring token & stream URL |
| `GET` | `/stream/{token}/{filename}` | Stream audio bytes directly from Telegram |

### Services

| File | Role |
|------|------|
| `app/services/track_resolver.py` | iTunes Search API |
| `app/services/apple_downloader.py` | Download from Apple Music (via aplmate) |
| `app/services/telegram_uploader.py` | Pyrogram `wzgram` client for uploading files |
| `app/services/token_service.py` | Create/validate expiring TTL tokens in Mongo |
| `app/services/streamer.py` | Optimized `ByteStreamer` using Pyrogram chunking |

### Database
- MongoDB Atlas (motor async).
- Collections: `tracks` (unique indexes on track_id & apple_track_id) and `stream_tokens` (TTL index on expires_at).

---

## Critical product decisions (do not regress)

1. **Memory Optimized Streamer:** The `ByteStreamer` in `app/services/streamer.py` uses `wzgram.Client.stream_media()` with calculated chunk offsets. DO NOT revert this to downloading to `io.BytesIO()`. The current approach enables instant playback seeking and near-zero memory footprint for large files.
2. **MongoDB Datetimes:** PyMongo strips timezone offsets on read. When comparing `expires_at` with `datetime.now(timezone.utc)`, the retrieved datetime must be made offset-aware (`doc["expires_at"].replace(tzinfo=timezone.utc)`).
3. **No direct file download endpoints:** Legacy `/tracks/download` was removed. The only way to get audio is via ingestion + stream link.

---

## Project structure

```
vynl-audio-streaming/
├── PLAN.md                 # Full architecture
├── CONTEXT.md              # This file
├── README.md               # Setup + test commands
├── app/
│   ├── main.py
│   ├── config.py
│   ├── exceptions.py
│   ├── api/
│   │   ├── stream.py       # Public stream endpoints
│   │   └── tracks.py       # REST API endpoints
│   ├── db/
│   │   └── mongo.py        # Motor DB client & queries
│   ├── models/
│   │   └── track.py        # Pydantic models
│   └── services/
│       ├── apple_downloader.py
│       ├── streamer.py
│       ├── telegram_uploader.py
│       └── token_service.py
├── requirements.txt
└── .env
```

---

## Environment variables (current)

```env
PORT=8000
BASE_URL=http://localhost:8000
ITUNES_SEARCH_COUNTRY=US
ITUNES_SEARCH_LIMIT=5
APL_MAX_RETRIES=3
DOWNLOAD_TIMEOUT=120

# Telegram
API_ID=...
API_HASH=...
BOT_TOKEN=...
STORAGE_CHANNEL_ID=...

# MongoDB
MONGO_URI=...
MONGO_DB=vynl_audio
STREAM_TOKEN_TTL=7200
```

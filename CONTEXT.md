# Project Context — vynl-audio-streaming

Handoff reference and architecture documentation for the VYNL audio streaming microservice.

---

## 1. Responsibilities

Pure backend microservice built with FastAPI providing audio search, download, and streaming capabilities:
- **Search & Candidate Discovery**: iTunes Search API integration via `app/services/track_resolver.py`.
- **Ingestion & Storage**: Resolves track candidates, downloads high-quality audio via `aplmate`, uploads directly to a private Telegram storage channel, and persists records in MongoDB (`vynl_audio.tracks`).
- **Stream Generation**: Issues expiring TTL tokens via `app/services/token_service.py` (`GET /api/v1/tracks/{track_id}/stream-link`).
- **High-Performance Audio Streaming**: Proxies audio bytes directly from Telegram CDN using chunk offsets in `ByteStreamer` (`app/services/streamer.py`).

---

## 2. API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check verifying Telegram and MongoDB connectivity |
| `GET` | `/api/v1/tracks/search` | Search iTunes for candidates by title and optional artist |
| `POST` | `/api/v1/tracks/resolve` | Resolve metadata for a candidate track |
| `POST` | `/api/v1/tracks/ingest` | Dedup check, download, Telegram upload, and MongoDB storage |
| `GET` | `/api/v1/tracks/{track_id}/stream-link` | Generate 2-hour expiring token and stream URL |
| `GET` | `/stream/{token}/{filename}` | Stream audio bytes directly from Telegram channel |

---

## 3. Database Architecture

- **Database**: `vynl_audio` (Motor async client)
- **Collections**:
  - `tracks`: Index on `track_id` (unique) and `apple_track_id` (unique).
  - `stream_tokens`: TTL index on `expires_at` for automatic expiration.

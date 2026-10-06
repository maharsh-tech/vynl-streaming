# vynl-audio-streaming

Backend microservice for Vynl: resolves song names → downloads MP3 → uploads to Telegram → proxies playback via an optimized ByteStreamer.

See [PLAN.md](./PLAN.md), [docs/PHASE1.md](./docs/PHASE1.md), and [docs/PHASE2.md](./docs/PHASE2.md).

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```
Fill in the Telegram credentials and MongoDB URI in `.env`.

## Run

```bash
uvicorn app.main:app --reload
```

Interactive Swagger UI: http://localhost:8000/docs

## Features / Endpoints

*   **`GET /api/v1/tracks/search`**: Search Apple Music by title/artist to get candidate matches.
*   **`POST /api/v1/tracks/resolve`**: Select a track to resolve exact metadata without downloading.
*   **`POST /api/v1/tracks/ingest`**: Provide a title/artist or an Apple Music URL. The backend will:
    1. Resolve the track.
    2. Check MongoDB for a dedup hit (returns instantly if already stored).
    3. Download the track from Apple Music (if new).
    4. Upload to a private Telegram Storage Channel (if new).
    5. Save the metadata and Telegram `file_id` in MongoDB.
*   **`GET /api/v1/tracks/{track_id}/stream-link`**: Retrieve a secure, time-limited URL for a stored track.
*   **`GET /stream/{token}/{filename}`**: The highly optimized `ByteStreamer` endpoint. It uses Pyrogram's chunk-offsetting to proxy bytes directly from Telegram to the client without buffering large files in memory, providing instant playback seeking.

## Testing (PowerShell)

You can test the entire ingestion and streaming flow from the terminal.

### 1. Ingest a Track
```powershell
$body = @{ title = "Blinding Lights"; artist = "The Weeknd" } | ConvertTo-Json
$response = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/tracks/ingest" `
  -ContentType "application/json" -Body $body
$response
```

### 2. Get a Stream Link
Copy the `track_id` from the previous response:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/tracks/{track_id}/stream-link"
```

### 3. Stream the Audio
Copy the `stream_url` from the previous response and paste it into your browser!

## Health

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

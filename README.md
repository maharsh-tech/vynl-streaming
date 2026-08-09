# vynl-audio-streaming

Backend microservice: resolve song names → download MP3 → store in Telegram.

See [PLAN.md](./PLAN.md), [docs/PHASE1.md](./docs/PHASE1.md), and [docs/PHASE2.md](./docs/PHASE2.md).

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with Telegram credentials (required for download):

```env
API_ID=
API_HASH=
BOT_TOKEN=
STORAGE_CHANNEL_ID=-100xxxxxxxxxx
```

Bot must be **admin** in your private storage channel.

## Run

```bash
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

## Phase 1 — Resolve Apple Music link

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/tracks/resolve" `
  -ContentType "application/json" `
  -Body '{"title":"Blinding Lights","artist":"The Weeknd"}'
```

## Phase 2 — Download + Telegram upload (testing)

`POST /api/v1/tracks/download` will:

1. Resolve song (if no `apple_music_url` given)
2. Download MP3 from aplmate
3. Upload to your private Telegram channel
4. **Return the MP3 file directly** (browser/Swagger downloads it)

Temp **stream URLs** from Telegram come in Phase 4 — not in this phase.

**Swagger:** use `POST /api/v1/tracks/download` with:

```json
{
  "title": "Daylight",
  "artist": "David Kushner"
}
```

Or with URL only:

```json
{
  "apple_music_url": "https://music.apple.com/us/album/daylight/..."
}
```

**PowerShell** (saves file):

```powershell
Invoke-WebRequest -Method POST -Uri "http://localhost:8000/api/v1/tracks/download" `
  -ContentType "application/json" `
  -Body '{"title":"Daylight","artist":"David Kushner"}' `
  -OutFile "daylight.mp3"
```

Response headers include Telegram storage refs: `X-Telegram-Chat-Id`, `X-Telegram-Msg-Id`.

Download usually takes **10–30 seconds** — wait for it to finish.

## Health

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

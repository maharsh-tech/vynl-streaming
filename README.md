# vynl-audio-streaming

Backend microservice for resolving song names to Apple Music links and downloading MP3 files (Phase 2 testing).

See [PLAN.md](./PLAN.md), [docs/PHASE1.md](./docs/PHASE1.md), and [docs/PHASE2.md](./docs/PHASE2.md).

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

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

## Phase 2 — Download MP3 (testing)

Step 1 — trigger download:

```powershell
$r = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/tracks/download" `
  -ContentType "application/json" `
  -Body '{"title":"Blinding Lights","artist":"The Weeknd"}'
$r
```

Step 2 — save the file locally:

```powershell
Invoke-WebRequest -Uri "http://localhost:8000$($r.download_url)" -OutFile "test.mp3"
```

Or download by Apple Music URL directly:

```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/tracks/download" `
  -ContentType "application/json" `
  -Body '{"apple_music_url":"https://music.apple.com/..."}'
```

**Note:** Phase 2 returns a **file download URL**, not a stream link. Temp stream URLs from Telegram storage come in Phase 4.

## Health

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

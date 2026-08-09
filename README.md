# vynl-audio-streaming

Backend microservice: resolve song names → download MP3 (Phase 2 testing).

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

`POST /api/v1/tracks/download` resolves (if needed), downloads the MP3, and **returns the file directly**.

No Telegram. No temp stream URLs yet — those come in later phases.

**Swagger:** `POST /api/v1/tracks/download`:

```json
{
  "title": "Daylight",
  "artist": "David Kushner"
}
```

Takes **10–30 seconds** — wait for it to finish, then the file downloads.

**PowerShell:**

```powershell
Invoke-WebRequest -Method POST -Uri "http://localhost:8000/api/v1/tracks/download" `
  -ContentType "application/json" `
  -Body '{"title":"Daylight","artist":"David Kushner"}' `
  -OutFile "daylight.mp3"
```

## Health

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

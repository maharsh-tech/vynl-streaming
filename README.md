# vynl-audio-streaming

Backend microservice for resolving song names to Apple Music links (Phase 1).

See [PLAN.md](./PLAN.md) and [docs/PHASE1.md](./docs/PHASE1.md).

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

## Phase 1 API

### Resolve song → Apple Music link

```bash
curl -X POST http://localhost:8000/api/v1/tracks/resolve \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Blinding Lights\",\"artist\":\"The Weeknd\"}"
```

### Search preview (optional)

```bash
curl "http://localhost:8000/api/v1/tracks/search?title=Blinding%20Lights&artist=The%20Weeknd"
```

### Health

```bash
curl http://localhost:8000/health
```

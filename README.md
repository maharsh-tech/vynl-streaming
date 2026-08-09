# vynl-audio-streaming

Backend microservice for ingesting Apple Music tracks and serving temporary stream URLs via Telegram storage.

See [PLAN.md](./PLAN.md) for architecture and API design.

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

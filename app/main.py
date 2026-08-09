from fastapi import FastAPI

app = FastAPI(title="vynl-audio-streaming")


@app.get("/health")
async def health():
    return {"status": "ok"}

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ResolveRequest(BaseModel):
    title: str = Field(..., min_length=1)
    artist: str | None = None


class ResolveResponse(BaseModel):
    title: str
    artist: str
    apple_track_id: int
    apple_music_url: str
    duration_ms: int | None = None
    artwork_url: str | None = None


class SearchCandidate(BaseModel):
    title: str
    artist: str
    apple_track_id: int
    apple_music_url: str
    duration_ms: int | None = None
    artwork_url: str | None = None


class DownloadRequest(BaseModel):
    title: str | None = None
    artist: str | None = None
    apple_music_url: str | None = None

    @model_validator(mode="after")
    def validate_input(self) -> "DownloadRequest":
        if self.apple_music_url:
            return self
        if self.title and self.title.strip():
            return self
        raise ValueError("Provide title or apple_music_url")


# ── Phase 3: Ingest ───────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    title: str | None = None
    artist: str | None = None
    apple_music_url: str | None = None
    apple_track_id: int | None = None

    @model_validator(mode="after")
    def validate_ingest_input(self) -> "IngestRequest":
        if self.apple_music_url:
            return self
        if self.title and self.title.strip():
            return self
        raise ValueError("Provide title or apple_music_url")


class IngestResponse(BaseModel):
    track_id: str
    title: str
    artist: str
    apple_track_id: int
    apple_music_url: str
    filename: str
    file_size: int
    duration_ms: int | None = None
    artwork_url: str | None = None
    status: str
    deduped: bool = False


class TelegramRef(BaseModel):
    chat_id: int
    msg_id: int
    file_id: str


class TrackInfoResponse(BaseModel):
    track_id: str
    title: str
    artist: str
    apple_track_id: int
    apple_music_url: str
    filename: str
    file_size: int
    duration_ms: int | None = None
    artwork_url: str | None = None
    status: str
    telegram: TelegramRef
    created_at: datetime
    updated_at: datetime


# ── Phase 4: Stream link ──────────────────────────────────────────────────────

class StreamLinkResponse(BaseModel):
    stream_url: str
    expires_at: datetime
    ttl_seconds: int


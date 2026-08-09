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


class DownloadResponse(BaseModel):
    title: str
    artist: str | None
    filename: str
    file_size: int
    apple_track_id: int | None
    apple_music_url: str
    download_url: str
    expires_at: datetime
    artwork_url: str | None = None

from pydantic import BaseModel, Field


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

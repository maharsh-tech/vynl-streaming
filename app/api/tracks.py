from fastapi import APIRouter, HTTPException, Query

from app.exceptions import TrackNotFoundError
from app.models.track import ResolveRequest, ResolveResponse, SearchCandidate
from app.services import track_resolver

router = APIRouter(tags=["tracks"])


@router.post("/tracks/resolve", response_model=ResolveResponse)
async def resolve_track(body: ResolveRequest) -> ResolveResponse:
    try:
        return await track_resolver.resolve_track(body.title, body.artist)
    except TrackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tracks/search", response_model=list[SearchCandidate])
async def search_tracks(
    title: str = Query(..., min_length=1),
    artist: str | None = Query(None),
) -> list[SearchCandidate]:
    results = await track_resolver.search_tracks(title, artist)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No Apple Music matches for: {title}",
        )
    return results

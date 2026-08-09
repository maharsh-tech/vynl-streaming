class TrackNotFoundError(Exception):
    """Raised when no Apple Music / iTunes match exists for the query."""


class DownloadError(Exception):
    """Raised when aplmate or CDN download fails."""


class MultiTrackError(Exception):
    """Raised when URL resolves to album/playlist (multiple tracks)."""


class FileNotReadyError(Exception):
    """Raised when a download file token is missing or expired."""

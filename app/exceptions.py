class TrackNotFoundError(Exception):
    """Raised when no Apple Music / iTunes match exists for the query."""


class DownloadError(Exception):
    """Raised when aplmate or CDN download fails."""


class MultiTrackError(Exception):
    """Raised when URL resolves to album/playlist (multiple tracks)."""


class FileNotReadyError(Exception):
    """Raised when a download file token is missing or expired."""


class StorageError(Exception):
    """Raised when Telegram upload or MongoDB write fails."""


class ServiceUnavailableError(Exception):
    """Raised when a required Phase 3+ dependency is not configured or started."""

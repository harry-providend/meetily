class MatchContextExtractor:
    """Trims a transcript segment to a window around the first match, for search result rows.

    Slices by character, not byte: the equivalent Rust helper indexes &str by byte offset, which
    panics when a multi-byte character straddles the boundary.
    """

    def __init__(self, window: int = 100, fallback_length: int = 200) -> None:
        self._window = window
        self._fallback_length = fallback_length

    def extract(self, transcript: str, query: str) -> str:
        position = transcript.lower().find(query.lower())
        if position < 0:
            return transcript[: self._fallback_length]

        start = max(0, position - self._window)
        end = min(len(transcript), position + len(query) + self._window)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(transcript) else ""
        return f"{prefix}{transcript[start:end]}{suffix}"

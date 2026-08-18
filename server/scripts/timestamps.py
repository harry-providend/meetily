"""Tolerant timestamp parsing for the SQLite backfill: one column holds several formats.
Unparseable values are reported, never defaulted to now()."""

from datetime import UTC, datetime

# Formats observed across the Rust call sites, tried in order.
_NAIVE_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)


class UnparseableTimestampError(ValueError):
    def __init__(self, raw: str) -> None:
        super().__init__(f"could not parse timestamp {raw!r}")
        self.raw = raw


def parse_timestamp(raw: str | None) -> datetime | None:
    """Aware UTC datetime, or None for NULL/blank. Naive values are treated as UTC -- the app
    writes UTC everywhere, it just doesn't always say so."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None

    try:
        # fromisoformat handles a trailing "Z" natively on the Python this project targets.
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = _try_explicit_formats(text)

    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _try_explicit_formats(text: str) -> datetime:
    for fmt in _NAIVE_FORMATS:
        try:
            # Naive by design: these formats carry no offset, and the caller attaches UTC.
            return datetime.strptime(text, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    raise UnparseableTimestampError(text)

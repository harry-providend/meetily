from datetime import UTC, datetime

import pytest
from scripts.timestamps import UnparseableTimestampError, parse_timestamp


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The three encodings the desktop app writes into the same logical column.
        ("2026-08-01T09:00:00+00:00", datetime(2026, 8, 1, 9, 0, tzinfo=UTC)),
        ("2026-08-01 09:00:00", datetime(2026, 8, 1, 9, 0, tzinfo=UTC)),
        ("2026-08-01T09:00:00.123456", datetime(2026, 8, 1, 9, 0, 0, 123456, tzinfo=UTC)),
        # Trailing Z, which fromisoformat rejects on older Pythons.
        ("2026-08-01T09:00:00Z", datetime(2026, 8, 1, 9, 0, tzinfo=UTC)),
    ],
)
def test_parses_every_observed_format(raw: str, expected: datetime) -> None:
    assert parse_timestamp(raw) == expected


def test_naive_values_are_treated_as_utc() -> None:
    parsed = parse_timestamp("2026-08-01 09:00:00")
    assert parsed is not None
    assert parsed.tzinfo is not None


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_missing_values_return_none(raw: str | None) -> None:
    assert parse_timestamp(raw) is None


def test_unparseable_values_raise_rather_than_defaulting_to_now() -> None:
    # Silently substituting now() would manufacture false history.
    with pytest.raises(UnparseableTimestampError):
        parse_timestamp("not-a-date")

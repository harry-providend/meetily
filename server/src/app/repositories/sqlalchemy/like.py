LIKE_ESCAPE = "\\"


def contains(value: str) -> str:
    """A LIKE pattern matching `value` literally, so a search for "50%" finds a percent sign
    rather than every row. Pair with `escape=LIKE_ESCAPE` on the comparison."""
    escaped = value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    for wildcard in ("%", "_"):
        escaped = escaped.replace(wildcard, LIKE_ESCAPE + wildcard)
    return f"%{escaped}%"

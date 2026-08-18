"""Refuses to run the destructive suites against a database whose name does not opt in. The
fixtures drop every table, so a development database pointed at here would be erased."""

import os

ENV_URL = "MEETILY_TEST_DATABASE_URL"
OVERRIDE = "MEETILY_ALLOW_DESTRUCTIVE_TESTS"
_SAFE_SUFFIXES = ("_test", "_tests", "test")


def require_disposable_database(url: str) -> str:
    """Returns the URL, or raises if its database name does not look disposable."""
    if os.environ.get(OVERRIDE) == "1":
        return url

    name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if name.endswith(_SAFE_SUFFIXES):
        return url

    raise RuntimeError(
        f"refusing to run destructive tests against database {name!r}: these suites drop every "
        f"table. Point {ENV_URL} at a database whose name ends in _test (createdb "
        f"{name}_test), omit it to use a throwaway container, or set {OVERRIDE}=1 to override."
    )

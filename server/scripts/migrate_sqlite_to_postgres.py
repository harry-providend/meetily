"""One-time SQLite -> Postgres backfill, run per environment cutover and rehearsed against a
copy first. The local schema has no ownership concept, so every meeting is attributed to the
owner passed in as --owner-oid / --owner-tenant-id.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \\
        --sqlite-path ~/Library/Application\\ Support/.../meetily.db \\
        --owner-oid <entra-object-id> --owner-tenant-id <entra-tenant-id> \\
        --database-url postgresql+asyncpg://... \\
        --audit-log ./cutover-audit.txt \\
        [--dry-run] [--acknowledge-dropped-tables]

Safe to re-run: aggregates merge on natural ids, version rows use ON CONFLICT DO NOTHING.
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from pydantic import JsonValue
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from app.domain.meeting import MeetingEntity
from app.domain.summary_process import SummaryProcessEntity
from app.domain.summary_version import SummaryVersionEntity
from app.domain.transcript import TranscriptEntity
from app.domain.transcript_version import TranscriptVersionEntity
from scripts.timestamps import UnparseableTimestampError, parse_timestamp

# Not ported, by decision: plaintext provider API keys, and licensing (referenced nowhere).
DROPPED_TABLES = ("settings", "transcript_settings", "licensing")


@dataclass
class Report:
    """What the run saw and what it refused to move. Counts and column names only -- never a
    secret value, so this file is safe to keep alongside a cutover ticket."""

    copied: dict[str, int] = field(default_factory=dict)
    dropped_table_rows: dict[str, int] = field(default_factory=dict)
    populated_secret_columns: list[str] = field(default_factory=list)
    unparseable_timestamps: list[str] = field(default_factory=list)
    orphaned_rows: dict[str, int] = field(default_factory=dict)
    duplicate_versions: list[str] = field(default_factory=list)

    def write(self, stream: TextIO) -> None:
        stream.write(f"cutover audit {datetime.now(UTC).isoformat()}\n\n")
        stream.write("copied:\n")
        stream.writelines(f"  {table}: {count}\n" for table, count in sorted(self.copied.items()))
        stream.write("\nnot ported (intentional):\n")
        stream.writelines(
            f"  {table}: {count} row(s)\n"
            for table, count in sorted(self.dropped_table_rows.items())
        )
        if self.populated_secret_columns:
            stream.write("\ncolumns holding credentials that will NOT be migrated:\n")
            stream.writelines(f"  {column}\n" for column in self.populated_secret_columns)
        if self.unparseable_timestamps:
            stream.write(f"\nquarantined timestamps ({len(self.unparseable_timestamps)}):\n")
            stream.writelines(f"  {raw!r}\n" for raw in self.unparseable_timestamps[:50])
        if self.orphaned_rows:
            stream.write("\nskipped rows with no surviving parent meeting:\n")
            stream.writelines(
                f"  {table}: {count}\n" for table, count in sorted(self.orphaned_rows.items())
            )
        if self.duplicate_versions:
            stream.write("\nBLOCKER -- duplicate (meeting_id, version) pairs:\n")
            stream.writelines(f"  {entry}\n" for entry in self.duplicate_versions)


class SqliteReader:
    def __init__(self, path: Path) -> None:
        self._connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self._connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self._connection.close()

    def table_exists(self, table: str) -> bool:
        cursor = self._connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        return cursor.fetchone() is not None

    def count(self, table: str) -> int:
        if not self.table_exists(table):
            return 0
        return int(self._connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])

    def columns(self, table: str) -> list[str]:
        if not self.table_exists(table):
            return []
        cursor = self._connection.execute(f"PRAGMA table_info({table})")
        return [str(row["name"]) for row in cursor.fetchall()]

    def rows(self, query: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        return list(self._connection.execute(query, params).fetchall())


class Migrator:
    def __init__(
        self,
        reader: SqliteReader,
        session: AsyncSession,
        owner_oid: str,
        owner_tenant_id: str,
        report: Report,
    ) -> None:
        self._reader = reader
        self._session = session
        self._owner_oid = owner_oid
        self._owner_tenant_id = owner_tenant_id
        self._report = report
        self._meeting_ids: set[str] = set()

    async def run(self) -> None:
        await self._copy_meetings()
        await self._copy_transcripts()
        await self._copy_summary_processes()
        await self._copy_versions()

    def _timestamp(self, raw: str | None, fallback: datetime) -> datetime:
        try:
            parsed = parse_timestamp(raw)
        except UnparseableTimestampError as exc:
            self._report.unparseable_timestamps.append(exc.raw)
            return fallback
        return parsed if parsed is not None else fallback

    async def _copy_meetings(self) -> None:
        now = datetime.now(UTC)
        rows = self._reader.rows("SELECT * FROM meetings")
        for row in rows:
            meeting_id = row["id"]
            if meeting_id is None:
                # Non-INTEGER SQLite primary keys do not imply NOT NULL; Postgres does.
                self._report.orphaned_rows["meetings (null id)"] = (
                    self._report.orphaned_rows.get("meetings (null id)", 0) + 1
                )
                continue
            created = self._timestamp(row["created_at"], now)
            await self._session.merge(
                MeetingEntity(
                    id=meeting_id,
                    owner_user_id=self._owner_oid,
                    owner_tenant_id=self._owner_tenant_id,
                    title=row["title"] or "",
                    folder_path=self._column(row, "folder_path"),
                    created_at=created,
                    updated_at=self._timestamp(row["updated_at"], created),
                )
            )
            self._meeting_ids.add(str(meeting_id))
        self._report.copied["meetings"] = len(self._meeting_ids)

    async def _copy_transcripts(self) -> None:
        copied = 0
        for meeting_id in sorted(self._meeting_ids):
            # rowid is the only record of segment order in SQLite and does not survive the
            # move, so per-meeting position becomes the explicit sequence_number.
            rows = self._reader.rows(
                "SELECT rowid AS _rowid, * FROM transcripts WHERE meeting_id = ? ORDER BY rowid",
                (meeting_id,),
            )
            for position, row in enumerate(rows, start=1):
                await self._session.merge(
                    TranscriptEntity(
                        id=row["id"],
                        meeting_id=meeting_id,
                        sequence_number=position,
                        transcript=row["transcript"] or "",
                        timestamp=row["timestamp"] or "",
                        summary=self._column(row, "summary"),
                        action_items=self._column(row, "action_items"),
                        key_points=self._column(row, "key_points"),
                        audio_start_time=self._column(row, "audio_start_time"),
                        audio_end_time=self._column(row, "audio_end_time"),
                        duration=self._column(row, "duration"),
                        speaker=self._column(row, "speaker"),
                    )
                )
                copied += 1
        self._report.copied["transcripts"] = copied
        self._count_orphans("transcripts")

    async def _copy_summary_processes(self) -> None:
        if not self._reader.table_exists("summary_processes"):
            return
        now = datetime.now(UTC)
        copied = 0
        for row in self._reader.rows("SELECT * FROM summary_processes"):
            if str(row["meeting_id"]) not in self._meeting_ids:
                continue
            created = self._timestamp(row["created_at"], now)
            await self._session.merge(
                SummaryProcessEntity(
                    meeting_id=row["meeting_id"],
                    status=row["status"] or "unknown",
                    created_at=created,
                    updated_at=self._timestamp(row["updated_at"], created),
                    error=self._column(row, "error"),
                    result=self._column(row, "result"),
                    start_time=self._optional_timestamp(row, "start_time"),
                    end_time=self._optional_timestamp(row, "end_time"),
                    chunk_count=self._column(row, "chunk_count") or 0,
                    processing_time=self._column(row, "processing_time") or 0.0,
                    process_metadata=self._json_object(self._column(row, "metadata")),
                )
            )
            copied += 1
        self._report.copied["summary_processes"] = copied
        self._count_orphans("summary_processes")

    async def _copy_versions(self) -> None:
        now = datetime.now(UTC)

        if self._reader.table_exists("transcript_versions"):
            copied = 0
            seen: set[tuple[str, int]] = set()
            for row in self._reader.rows("SELECT * FROM transcript_versions"):
                meeting_id = str(row["meeting_id"])
                if meeting_id not in self._meeting_ids:
                    continue
                key = (meeting_id, int(row["version"]))
                if key in seen:
                    # Would violate UNIQUE(meeting_id, version). Surface it, don't auto-dedup.
                    self._report.duplicate_versions.append(f"transcript_versions {key}")
                    continue
                seen.add(key)
                # Derived-string ids are dropped for a surrogate key. DO NOTHING so a re-run
                # after a partial cutover skips existing rows instead of failing.
                await self._session.execute(
                    pg_insert(TranscriptVersionEntity)
                    .values(
                        meeting_id=meeting_id,
                        version=int(row["version"]),
                        reason=row["reason"] or "",
                        segments_json=self._json_array(self._column(row, "segments_json")),
                        segment_count=self._column(row, "segment_count") or 0,
                        created_at=self._timestamp(row["created_at"], now),
                    )
                    .on_conflict_do_nothing(index_elements=["meeting_id", "version"])
                )
                copied += 1
            self._report.copied["transcript_versions"] = copied

        if self._reader.table_exists("summary_versions"):
            copied = 0
            seen_summary: set[tuple[str, int]] = set()
            for row in self._reader.rows("SELECT * FROM summary_versions"):
                meeting_id = str(row["meeting_id"])
                if meeting_id not in self._meeting_ids:
                    continue
                key = (meeting_id, int(row["version"]))
                if key in seen_summary:
                    self._report.duplicate_versions.append(f"summary_versions {key}")
                    continue
                seen_summary.add(key)
                await self._session.execute(
                    pg_insert(SummaryVersionEntity)
                    .values(
                        meeting_id=meeting_id,
                        version=int(row["version"]),
                        reason=row["reason"] or "",
                        result_json=self._json_object(self._column(row, "result_json")) or {},
                        created_at=self._timestamp(row["created_at"], now),
                    )
                    .on_conflict_do_nothing(index_elements=["meeting_id", "version"])
                )
                copied += 1
            self._report.copied["summary_versions"] = copied

    def _count_orphans(self, table: str) -> None:
        if not self._reader.table_exists(table):
            return
        total = self._reader.count(table)
        rows = self._reader.rows(f"SELECT meeting_id FROM {table}")
        orphans = sum(1 for row in rows if str(row["meeting_id"]) not in self._meeting_ids)
        if orphans:
            # Parent meeting gone: would violate the FK, so count and skip, don't abort.
            self._report.orphaned_rows[table] = orphans
        assert total >= orphans

    def _optional_timestamp(self, row: sqlite3.Row, column: str) -> datetime | None:
        raw = self._column(row, column)
        if raw is None:
            return None
        try:
            return parse_timestamp(str(raw))
        except UnparseableTimestampError as exc:
            self._report.unparseable_timestamps.append(exc.raw)
            return None

    @staticmethod
    def _column(row: sqlite3.Row, name: str) -> object:
        # .keys() is required: sqlite3.Row.__contains__ tests values, not column names.
        return row[name] if name in row.keys() else None  # noqa: SIM118

    @staticmethod
    def _json_object(raw: object) -> dict[str, JsonValue] | None:
        if raw is None:
            return None
        try:
            parsed: JsonValue = json.loads(str(raw))
        except json.JSONDecodeError:
            return {"raw": str(raw)}
        return parsed if isinstance(parsed, dict) else {"raw": parsed}

    @staticmethod
    def _json_array(raw: object) -> list[JsonValue]:
        if raw is None:
            return []
        try:
            parsed: JsonValue = json.loads(str(raw))
        except json.JSONDecodeError:
            return [{"raw": str(raw)}]
        return parsed if isinstance(parsed, list) else [parsed]


def audit_dropped_tables(reader: SqliteReader, report: Report) -> None:
    for table in DROPPED_TABLES:
        report.dropped_table_rows[table] = reader.count(table)
        for column in reader.columns(table):
            if "apikey" not in column.lower().replace("_", "") and column != "customOpenAIConfig":
                continue
            populated = reader.rows(
                f'SELECT count(*) AS n FROM {table} WHERE "{column}" IS NOT NULL '
                f'AND "{column}" != ""'
            )
            if populated and int(populated[0]["n"]) > 0:
                report.populated_secret_columns.append(f"{table}.{column}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-path", required=True, type=Path)
    parser.add_argument("--owner-oid", required=True)
    parser.add_argument("--owner-tenant-id", required=True)
    parser.add_argument("--database-url")
    parser.add_argument("--audit-log", type=Path, default=Path("cutover-audit.txt"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="produce the audit report and copy nothing",
    )
    parser.add_argument(
        "--acknowledge-dropped-tables",
        action="store_true",
        help="confirm the operator has read the audit report and accepts that settings, "
        "transcript_settings, and licensing will not be migrated",
    )
    args = parser.parse_args()

    if not args.sqlite_path.exists():
        print(f"no such SQLite file: {args.sqlite_path}", file=sys.stderr)
        return 2

    reader = SqliteReader(args.sqlite_path)
    report = Report()
    try:
        audit_dropped_tables(reader, report)

        if args.dry_run:
            report.copied = {
                table: reader.count(table)
                for table in (
                    "meetings",
                    "transcripts",
                    "summary_processes",
                    "transcript_versions",
                    "summary_versions",
                )
            }
        else:
            if not args.database_url:
                print("--database-url is required unless --dry-run", file=sys.stderr)
                return 2
            if not args.acknowledge_dropped_tables:
                print(
                    "refusing to run: re-run with --dry-run, read the audit report, then pass "
                    "--acknowledge-dropped-tables to confirm the dropped tables are expected",
                    file=sys.stderr,
                )
                return 3

            engine = create_async_engine(args.database_url)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                migrator = Migrator(reader, session, args.owner_oid, args.owner_tenant_id, report)
                await migrator.run()
                if report.duplicate_versions:
                    await session.rollback()
                    print(
                        "aborted: duplicate (meeting_id, version) rows need manual review",
                        file=sys.stderr,
                    )
                else:
                    await session.commit()
            await engine.dispose()
    finally:
        reader.close()

    with args.audit_log.open("w") as stream:
        report.write(stream)
    report.write(sys.stdout)

    return 1 if report.duplicate_versions else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

#!/usr/bin/env python3
"""Select the newest valid checkpoint chain for distinct Codex threads."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


INDEX_ROW_RE = re.compile(
    r"^\| `(?P<thread_id>[^`]*)` \| (?P<save_seq>\d+) \| "
    r"(?P<mode>full|incremental) \| `(?P<timestamp>\d{6}-\d{6})` \| "
    r"`(?P<slug>[^`]*)` \| \[[^]]*\]\((?P<path>[^)]+)\) \| "
    r"(?P<summary>.*) \|$"
)
THREAD_CELL_RE = re.compile(r"^\| `(?P<thread_id>[^`]*)` \|")
MARKER_RE = re.compile(
    r"^session: thread_id=(?P<thread_id>\S+) "
    r"save_seq=(?P<save_seq>\d+) "
    r"mode=(?P<mode>full|incremental) "
    r"previous=(?P<previous>\S+)$"
)
INDEX_HEADER = """# Session Log Index

| Thread ID | Save Seq | Mode | Timestamp | Slug | Path | Summary |
| --- | ---: | --- | --- | --- | --- | --- |
"""
REQUIRED_HEADINGS = (
    "# Summary",
    "## Goal",
    "## Context",
    "## Key Decisions",
    "## Work Performed",
    "## Files Changed",
    "## Validation",
    "## Open Questions / Next Steps",
)


@dataclass(frozen=True)
class IndexRow:
    """One parsed index row."""

    thread_id: str
    save_seq: int
    mode: str
    timestamp: str
    relative_path: str
    summary: str
    line_number: int


@dataclass(frozen=True)
class Marker:
    """Checkpoint metadata read from one session log."""

    thread_id: str
    save_seq: int
    mode: str
    previous: str


@dataclass(frozen=True)
class SelectedThread:
    """The ordered checkpoint chain for one resumable thread."""

    thread_id: str
    latest_save_seq: int
    latest_timestamp: str
    latest_path: str
    chain_paths: list[str]


@dataclass(frozen=True)
class SkippedItem:
    """One unavailable or damaged thread candidate."""

    thread_id: str | None
    path: str | None
    reason: str


def positive_integer(value: str) -> int:
    """Parse a strictly positive integer."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("count must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Select recent valid session state for distinct threads."
    )
    parser.add_argument(
        "--count",
        type=positive_integer,
        default=3,
        help="Number of distinct thread states to select. Defaults to 3.",
    )
    parser.add_argument(
        "--start",
        default=".",
        help="Start directory for upward index discovery. Defaults to cwd.",
    )
    parser.add_argument(
        "--workspace",
        help="Optional active-workspace fallback when upward discovery finds no index.",
    )
    return parser


def validate_index_path(path: Path) -> Path:
    """Require a regular, readable, non-symlink index file."""
    if path.is_symlink() or not path.is_file() or not os.access(path, os.R_OK):
        raise ValueError(f"session index is not a regular readable file: {path}")
    return path.resolve()


def discover_index(start: Path, workspace: Path | None) -> Path | None:
    """Find the nearest ancestor index, then an explicit workspace fallback."""
    start = start.expanduser().resolve()
    if start.is_file():
        start = start.parent
    for directory in (start, *start.parents):
        candidate = directory / "docs" / "sessions" / "index.md"
        if candidate.exists() or candidate.is_symlink():
            return validate_index_path(candidate)

    if workspace is not None:
        candidate = workspace.expanduser().resolve() / "docs" / "sessions" / "index.md"
        if candidate.exists() or candidate.is_symlink():
            return validate_index_path(candidate)
    return None


def read_locked(path: Path) -> str:
    """Read an index while holding a shared process lock."""
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    index_fd = os.open(path, flags)
    if not stat.S_ISREG(os.fstat(index_fd).st_mode):
        os.close(index_fd)
        raise ValueError(f"session index is not a regular file: {path}")
    with os.fdopen(index_fd, "r", encoding="utf-8") as index_file:
        fcntl.flock(index_file.fileno(), fcntl.LOCK_SH)
        try:
            return index_file.read()
        finally:
            fcntl.flock(index_file.fileno(), fcntl.LOCK_UN)


def parse_index(text: str) -> tuple[list[IndexRow], list[SkippedItem], set[str]]:
    """Parse usable rows and retain diagnostics for malformed data rows."""
    if text and not text.startswith(INDEX_HEADER):
        raise ValueError("session index header is missing or incompatible")
    rows: list[IndexRow] = []
    skipped: list[SkippedItem] = []
    corrupt_threads: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("| `"):
            continue
        match = INDEX_ROW_RE.fullmatch(line)
        if match is None:
            thread_match = THREAD_CELL_RE.match(line)
            thread_id = thread_match.group("thread_id") if thread_match else None
            if thread_id:
                corrupt_threads.add(thread_id)
            skipped.append(
                SkippedItem(
                    thread_id=thread_id,
                    path=None,
                    reason=f"malformed index row at line {line_number}",
                )
            )
            continue
        rows.append(
            IndexRow(
                thread_id=match.group("thread_id"),
                save_seq=int(match.group("save_seq")),
                mode=match.group("mode"),
                timestamp=match.group("timestamp"),
                relative_path=match.group("path"),
                summary=match.group("summary").replace("\\|", "|"),
                line_number=line_number,
            )
        )
    return rows, skipped, corrupt_threads


def is_invalid_text(text: str) -> bool:
    """Recognize explicit invalidation or supersession markers."""
    lowered = text.lower()
    prefixes = (
        "status: invalid",
        "status=invalid",
        "status: superseded",
        "status=superseded",
        "checkpoint status: invalid",
        "checkpoint status: superseded",
        "superseded by",
    )
    phrases = (
        "本对话已由用户明确判定为失效",
        "本会话已由用户明确判定为失效",
        "不能作为后续",
        "不可作为后续",
    )
    return any(
        line.strip().startswith(prefixes) for line in lowered.splitlines()
    ) or any(phrase in lowered for phrase in phrases)


def resolve_log_path(docs_dir: Path, relative_path: str) -> Path:
    """Resolve one regular readable file strictly within docs/sessions."""
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe session path: {relative_path}")

    candidate = docs_dir / relative
    current = docs_dir
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"session path uses a symlink: {relative_path}")

    resolved = candidate.resolve()
    try:
        resolved.relative_to(docs_dir.resolve())
    except ValueError as exc:
        raise ValueError(
            f"session path escapes docs/sessions: {relative_path}"
        ) from exc
    if not resolved.is_file() or not os.access(resolved, os.R_OK):
        raise ValueError(f"session log is missing or unreadable: {relative_path}")
    return resolved


def read_checkpoint(path: Path) -> tuple[Marker, str]:
    """Read one checkpoint and parse its line-12 marker."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if len(lines) < 14:
        raise ValueError(f"session log has no marker: {path.name}")
    if any(not line.strip() for line in lines[:10]) or lines[10].strip():
        raise ValueError(f"session log has an invalid 10-line opening: {path.name}")
    match = MARKER_RE.fullmatch(lines[11])
    if match is None:
        raise ValueError(f"session log has an invalid marker: {path.name}")
    if lines[12].strip():
        raise ValueError(
            f"session log marker is not separated from its body: {path.name}"
        )
    headings = [line for line in lines[13:] if line in REQUIRED_HEADINGS]
    if tuple(headings) != REQUIRED_HEADINGS or lines[13] != "# Summary":
        raise ValueError(f"session log has an invalid section structure: {path.name}")
    return (
        Marker(
            thread_id=match.group("thread_id"),
            save_seq=int(match.group("save_seq")),
            mode=match.group("mode"),
            previous=match.group("previous"),
        ),
        text,
    )


def build_chain(
    latest: IndexRow,
    rows_by_path: dict[str, list[IndexRow]],
    rows_by_thread_seq: dict[tuple[str, int], list[IndexRow]],
    docs_dir: Path,
) -> SelectedThread:
    """Validate and order a latest checkpoint's chain from full to newest."""
    current = latest
    seen: set[str] = set()
    reverse_paths: list[str] = []
    while True:
        if current.relative_path in seen:
            raise ValueError("checkpoint chain contains a cycle")
        seen.add(current.relative_path)
        if len(rows_by_path.get(current.relative_path, [])) != 1:
            raise ValueError(f"checkpoint path is duplicated: {current.relative_path}")
        if len(rows_by_thread_seq.get((current.thread_id, current.save_seq), [])) != 1:
            raise ValueError(f"checkpoint sequence is duplicated: {current.save_seq}")

        path = resolve_log_path(docs_dir, current.relative_path)
        marker, text = read_checkpoint(path)
        if is_invalid_text(current.summary) or is_invalid_text(
            "\n".join(text.splitlines()[:20])
        ):
            raise ValueError(
                f"checkpoint is explicitly invalid or superseded: {path.name}"
            )
        if (
            marker.thread_id != current.thread_id
            or marker.save_seq != current.save_seq
            or marker.mode != current.mode
        ):
            raise ValueError(f"index and marker disagree for {current.relative_path}")

        reverse_paths.append(str(path))
        if current.mode == "full":
            break
        if marker.previous == "none":
            raise ValueError("incremental checkpoint has no predecessor")

        predecessors = rows_by_path.get(marker.previous, [])
        if len(predecessors) != 1:
            raise ValueError(f"predecessor is missing or ambiguous: {marker.previous}")
        predecessor = predecessors[0]
        if predecessor.relative_path in seen:
            raise ValueError("checkpoint chain contains a cycle")
        if predecessor.thread_id != latest.thread_id:
            raise ValueError("checkpoint predecessor belongs to another thread")
        if predecessor.save_seq != current.save_seq - 1:
            raise ValueError("checkpoint sequence is not contiguous")
        current = predecessor

    return SelectedThread(
        thread_id=latest.thread_id,
        latest_save_seq=latest.save_seq,
        latest_timestamp=latest.timestamp,
        latest_path=str(resolve_log_path(docs_dir, latest.relative_path)),
        chain_paths=list(reversed(reverse_paths)),
    )


def select_threads(index_path: Path, count: int) -> dict[str, object]:
    """Select up to count newest valid distinct-thread states."""
    docs_dir = index_path.parent
    rows, skipped, corrupt_threads = parse_index(read_locked(index_path))
    rows_by_path: dict[str, list[IndexRow]] = {}
    rows_by_thread_seq: dict[tuple[str, int], list[IndexRow]] = {}
    maximum_sequence: dict[str, int] = {}
    for row in rows:
        rows_by_path.setdefault(row.relative_path, []).append(row)
        rows_by_thread_seq.setdefault((row.thread_id, row.save_seq), []).append(row)
        maximum_sequence[row.thread_id] = max(
            maximum_sequence.get(row.thread_id, 0), row.save_seq
        )

    selected: list[SelectedThread] = []
    seen_threads: set[str] = set()
    for latest in reversed(rows):
        if latest.thread_id in seen_threads:
            continue
        seen_threads.add(latest.thread_id)
        if latest.thread_id in corrupt_threads:
            skipped.append(
                SkippedItem(
                    thread_id=latest.thread_id,
                    path=latest.relative_path,
                    reason="thread has a malformed index row",
                )
            )
            continue
        if latest.save_seq != maximum_sequence[latest.thread_id]:
            skipped.append(
                SkippedItem(
                    thread_id=latest.thread_id,
                    path=latest.relative_path,
                    reason="thread index sequence is not append-monotonic",
                )
            )
            continue
        try:
            selected.append(
                build_chain(latest, rows_by_path, rows_by_thread_seq, docs_dir)
            )
        except (OSError, UnicodeError, ValueError) as exc:
            skipped.append(
                SkippedItem(
                    thread_id=latest.thread_id,
                    path=latest.relative_path,
                    reason=str(exc),
                )
            )
            continue
        if len(selected) == count:
            break

    return {
        "index_path": str(index_path),
        "requested_count": count,
        "selected_count": len(selected),
        "threads": [asdict(thread) for thread in selected],
        "skipped": [asdict(item) for item in skipped],
    }


def print_json(value: object) -> None:
    """Print stable JSON for the calling Skill."""
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def main() -> int:
    """Discover the index and print selected checkpoint chains."""
    args = build_parser().parse_args()
    try:
        workspace = Path(args.workspace) if args.workspace else None
        index_path = discover_index(Path(args.start), workspace)
        if index_path is None:
            print_json(
                {
                    "index_path": None,
                    "requested_count": args.count,
                    "selected_count": 0,
                    "threads": [],
                    "skipped": [],
                }
            )
            return 0
        print_json(select_threads(index_path, args.count))
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

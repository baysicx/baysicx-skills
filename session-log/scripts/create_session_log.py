#!/usr/bin/env python3
"""Inspect and publish thread-aware session checkpoints."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TextIO


TIMESTAMP_RE = re.compile(r"^\d{6}-\d{6}$")
THREAD_ID_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
INDEX_ROW_RE = re.compile(
    r"^\| `(?P<thread_id>[^`]*)` \| (?P<save_seq>\d+) \| "
    r"(?P<mode>full|incremental) \| `(?P<timestamp>\d{6}-\d{6})` \| "
    r"`(?P<slug>[^`]*)` \| \[[^]]*\]\((?P<path>[^)]+)\) \| "
    r"(?P<summary>.*) \|$"
)
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
MAX_INCREMENTALS = 2


@dataclass(frozen=True)
class IndexRow:
    """One parsed row from the session index."""

    thread_id: str
    save_seq: int
    mode: str
    timestamp: str
    slug: str
    relative_path: str
    summary: str
    line_number: int


@dataclass(frozen=True)
class Marker:
    """Checkpoint metadata embedded in a session log."""

    thread_id: str
    save_seq: int
    mode: str
    previous: str


@dataclass(frozen=True)
class ChainState:
    """Validated state of the latest checkpoint chain for one thread."""

    valid: bool
    consecutive_incrementals: int
    detail: str


@dataclass(frozen=True)
class Inspection:
    """Read-only recommendation for the next checkpoint."""

    thread_id: str
    next_save_seq: int
    previous: str
    consecutive_incrementals: int
    chain_valid: bool
    requested_mode: str
    recommended_mode: str
    reason: str


def normalize_slug(value: str) -> str:
    """Normalize a topic slug for a session-log filename."""
    slug = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "session-log"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Inspect or write a thread-aware session checkpoint."
    )
    parser.add_argument(
        "--slug",
        help="Topic slug for the filename; required when writing.",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root containing docs/sessions. Defaults to cwd.",
    )
    parser.add_argument(
        "--timestamp",
        help="Optional YYMMDD-HHMMSS override for tests or reproducible output.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "full", "incremental"),
        help="Requested mode. Inspection defaults to auto; writing defaults to full.",
    )
    parser.add_argument(
        "--thread-id",
        help="Explicit thread ID. Defaults to CODEX_THREAD_ID.",
    )
    parser.add_argument(
        "--expected-previous",
        help="Abort writing unless the latest indexed path still matches this value.",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print the next-checkpoint recommendation as JSON without writing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the successful write result as JSON instead of only the path.",
    )
    return parser


def resolve_timestamp(value: str | None) -> str:
    """Resolve and validate a filename timestamp."""
    if value is None:
        return datetime.now().strftime("%y%m%d-%H%M%S")
    if not TIMESTAMP_RE.fullmatch(value):
        raise ValueError(
            "--timestamp must match YYMMDD-HHMMSS, for example 260713-153045"
        )
    return value


def resolve_thread_id(value: str | None) -> str:
    """Resolve a safe thread ID from an argument or the Codex environment."""
    thread_id = (value or os.environ.get("CODEX_THREAD_ID", "")).strip()
    if not thread_id:
        raise ValueError(
            "thread ID is required; set CODEX_THREAD_ID or pass --thread-id"
        )
    if not THREAD_ID_RE.fullmatch(thread_id):
        raise ValueError("thread ID contains unsupported characters")
    return thread_id


def markdown_cell(value: str) -> str:
    """Escape text for an ordinary Markdown table cell."""
    return value.replace("\n", " ").replace("|", "\\|").strip()


def parse_index(text: str, *, strict: bool) -> list[IndexRow]:
    """Parse the current index while preserving append order."""
    if not text:
        return []
    if not text.startswith(INDEX_HEADER):
        raise ValueError("session index header is missing or incompatible")
    if not text.endswith("\n"):
        raise ValueError("session index must end with a newline")

    rows: list[IndexRow] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.startswith("| `"):
            continue
        match = INDEX_ROW_RE.fullmatch(line)
        if match is None:
            if strict:
                raise ValueError(f"invalid session index row at line {line_number}")
            continue
        rows.append(
            IndexRow(
                thread_id=match.group("thread_id"),
                save_seq=int(match.group("save_seq")),
                mode=match.group("mode"),
                timestamp=match.group("timestamp"),
                slug=match.group("slug"),
                relative_path=match.group("path"),
                summary=match.group("summary").replace("\\|", "|"),
                line_number=line_number,
            )
        )
    return rows


def latest_thread_row(rows: list[IndexRow], thread_id: str) -> IndexRow | None:
    """Return the newest indexed row for one thread."""
    matches = [row for row in rows if row.thread_id == thread_id]
    if not matches:
        return None
    return max(matches, key=lambda row: (row.save_seq, row.line_number))


def next_save_seq(rows: list[IndexRow], thread_id: str) -> int:
    """Return the next monotonically increasing save sequence."""
    sequences = [row.save_seq for row in rows if row.thread_id == thread_id]
    return max(sequences, default=0) + 1


def resolve_log_path(docs_dir: Path, relative_path: str) -> Path:
    """Resolve one regular readable log without leaving docs/sessions."""
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


def read_marker(path: Path) -> Marker:
    """Validate a stored checkpoint and parse its line-12 marker."""
    lines = path.read_text(encoding="utf-8").splitlines()
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
    if is_invalid_summary("\n".join(lines[:20])):
        raise ValueError(f"session log is explicitly invalid: {path.name}")
    return Marker(
        thread_id=match.group("thread_id"),
        save_seq=int(match.group("save_seq")),
        mode=match.group("mode"),
        previous=match.group("previous"),
    )


def is_invalid_summary(summary: str) -> bool:
    """Recognize an explicit self-invalidation without broad topic heuristics."""
    lowered = summary.lower()
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
    return lowered.strip().startswith(prefixes) or any(
        phrase in lowered for phrase in phrases
    )


def inspect_chain(rows: list[IndexRow], docs_dir: Path, thread_id: str) -> ChainState:
    """Validate the latest chain and count incrementals after its full anchor."""
    latest = latest_thread_row(rows, thread_id)
    if latest is None:
        return ChainState(False, 0, "no previous checkpoint")
    if is_invalid_summary(latest.summary):
        return ChainState(False, 0, "latest checkpoint is explicitly invalid")

    rows_by_path: dict[str, list[IndexRow]] = {}
    rows_by_thread_seq: dict[tuple[str, int], list[IndexRow]] = {}
    for row in rows:
        rows_by_path.setdefault(row.relative_path, []).append(row)
        rows_by_thread_seq.setdefault((row.thread_id, row.save_seq), []).append(row)

    current = latest
    seen: set[str] = set()
    incrementals = 0
    try:
        while True:
            if current.relative_path in seen:
                raise ValueError("checkpoint chain contains a cycle")
            seen.add(current.relative_path)
            if is_invalid_summary(current.summary):
                raise ValueError("checkpoint chain contains an invalid log")
            if len(rows_by_path.get(current.relative_path, [])) != 1:
                raise ValueError(
                    f"checkpoint path is duplicated: {current.relative_path}"
                )
            if (
                len(rows_by_thread_seq.get((current.thread_id, current.save_seq), []))
                != 1
            ):
                raise ValueError(
                    f"checkpoint sequence is duplicated: {current.save_seq}"
                )
            path = resolve_log_path(docs_dir, current.relative_path)
            marker = read_marker(path)
            if (
                marker.thread_id != current.thread_id
                or marker.save_seq != current.save_seq
                or marker.mode != current.mode
            ):
                raise ValueError(
                    f"index and marker disagree for {current.relative_path}"
                )
            if current.mode == "full":
                return ChainState(True, incrementals, "checkpoint chain is complete")

            incrementals += 1
            if marker.previous == "none":
                raise ValueError("incremental checkpoint has no predecessor")
            predecessors = rows_by_path.get(marker.previous, [])
            if len(predecessors) != 1:
                raise ValueError(
                    f"predecessor is missing or ambiguous: {marker.previous}"
                )
            predecessor = predecessors[0]
            if predecessor.thread_id != thread_id:
                raise ValueError("checkpoint predecessor belongs to another thread")
            if predecessor.save_seq != current.save_seq - 1:
                raise ValueError("checkpoint sequence is not contiguous")
            current = predecessor
    except (OSError, UnicodeError, ValueError) as exc:
        return ChainState(False, 0, str(exc))


def resolve_mode(requested_mode: str, chain: ChainState) -> tuple[str, str]:
    """Resolve auto or requested incremental mode to a safe stored mode."""
    if requested_mode == "full":
        return "full", "full mode was requested"
    if not chain.valid:
        return "full", chain.detail
    if chain.consecutive_incrementals >= MAX_INCREMENTALS:
        return "full", f"full anchor required after {MAX_INCREMENTALS} incrementals"
    if requested_mode == "incremental":
        return "incremental", "incremental mode was requested"
    return "incremental", "continuing a valid checkpoint chain"


def inspect_rows(
    rows: list[IndexRow],
    docs_dir: Path,
    thread_id: str,
    requested_mode: str,
) -> Inspection:
    """Build the next-checkpoint inspection result."""
    latest = latest_thread_row(rows, thread_id)
    previous = latest.relative_path if latest is not None else "none"
    chain = inspect_chain(rows, docs_dir, thread_id)
    recommended_mode, reason = resolve_mode(requested_mode, chain)
    return Inspection(
        thread_id=thread_id,
        next_save_seq=next_save_seq(rows, thread_id),
        previous=previous,
        consecutive_incrementals=chain.consecutive_incrementals,
        chain_valid=chain.valid,
        requested_mode=requested_mode,
        recommended_mode=recommended_mode,
        reason=reason,
    )


def validate_body(body: str) -> tuple[list[str], list[str]]:
    """Validate the model-authored summary structure before any write."""
    text = body
    if not text.strip():
        raise ValueError("session log body must not be empty")
    lines = text.splitlines()
    if len(lines) < 10 or any(not line.strip() for line in lines[:10]):
        raise ValueError("the first 10 summary lines must exist and contain no blanks")
    if any(
        line.lstrip().startswith(("#", "|", "-", "*", "```")) for line in lines[:10]
    ):
        raise ValueError(
            "the first 10 summary lines must be natural-language sentences"
        )

    tail = lines[10:]
    while tail and not tail[0].strip():
        tail.pop(0)
    actual_headings = [line for line in tail if line in REQUIRED_HEADINGS]
    if tuple(actual_headings) != REQUIRED_HEADINGS:
        raise ValueError(
            "session log body must contain the required headings once and in order"
        )
    if not tail or tail[0] != "# Summary":
        raise ValueError(
            "session log body must begin its structured section with # Summary"
        )
    return lines[:10], tail


def prepare_body(body: str, marker: str) -> tuple[str, str]:
    """Insert the generated marker into a validated body."""
    opening, tail = validate_body(body)
    content_lines = opening + ["", marker, ""] + tail
    return "\n".join(content_lines).rstrip() + "\n", opening[0].strip()


def format_index_row(
    *,
    thread_id: str,
    save_seq: int,
    mode: str,
    timestamp: str,
    slug: str,
    relative_path: str,
    summary: str,
) -> str:
    """Format one canonical session-index row."""
    return (
        f"| `{markdown_cell(thread_id)}` | {save_seq} | {mode} | `{timestamp}` | "
        f"`{markdown_cell(slug)}` | [{markdown_cell(relative_path)}]({relative_path}) | "
        f"{markdown_cell(summary)} |\n"
    )


def write_log_exclusive(
    docs_dir: Path, timestamp: str, slug: str, content: str
) -> Path:
    """Create a complete log without replacing an existing checkpoint."""
    suffix = 1
    while True:
        filename = (
            f"{timestamp}-{slug}.md"
            if suffix == 1
            else f"{timestamp}-{slug}-{suffix}.md"
        )
        output_path = docs_dir / filename
        try:
            output_file = output_path.open("x", encoding="utf-8", newline="\n")
        except FileExistsError:
            suffix += 1
            continue
        try:
            with output_file:
                output_file.write(content)
                output_file.flush()
                os.fsync(output_file.fileno())
            return output_path
        except BaseException as write_error:
            rollback_file(output_path, write_error)
            raise


def rollback_file(path: Path, primary: BaseException) -> None:
    """Remove a file created by the failed transaction without hiding failure."""
    try:
        path.unlink(missing_ok=True)
    except OSError as cleanup_error:
        raise RuntimeError(
            f"session publication failed and cleanup also failed for {path}: {cleanup_error}"
        ) from primary


def read_index_for_inspection(index_path: Path) -> str:
    """Read a regular index under a shared process lock."""
    if not index_path.exists():
        return ""
    if (
        index_path.is_symlink()
        or not index_path.is_file()
        or not os.access(index_path, os.R_OK)
    ):
        raise ValueError("session index must be a regular readable file")
    with index_path.open("r", encoding="utf-8") as index_file:
        fcntl.flock(index_file.fileno(), fcntl.LOCK_SH)
        try:
            return index_file.read()
        finally:
            fcntl.flock(index_file.fileno(), fcntl.LOCK_UN)


def append_index_locked(index_file: TextIO, index_text: str, row: str) -> None:
    """Append and verify one row, restoring the prior bytes on failure."""
    original_size = os.fstat(index_file.fileno()).st_size
    try:
        index_file.seek(0, os.SEEK_END)
        if not index_text:
            index_file.write(INDEX_HEADER)
        index_file.write(row)
        index_file.flush()
        os.fsync(index_file.fileno())
        index_file.seek(0)
        if not index_file.read().endswith(row):
            raise OSError("session index read-back did not contain the new row")
    except BaseException as publish_error:
        try:
            index_file.flush()
            os.ftruncate(index_file.fileno(), original_size)
            os.fsync(index_file.fileno())
        except OSError as rollback_error:
            raise RuntimeError(
                "session index publication failed and rollback also failed: "
                f"{rollback_error}"
            ) from publish_error
        raise


def publish(
    *,
    workspace: Path,
    thread_id: str,
    slug: str,
    timestamp: str,
    requested_mode: str,
    expected_previous: str | None,
    body: str,
) -> dict[str, object]:
    """Publish one log and its index row as a locked transaction."""
    validate_body(body)
    docs_dir = workspace / "docs" / "sessions"
    docs_dir.mkdir(parents=True, exist_ok=True)
    index_path = docs_dir / "index.md"
    if index_path.exists() and (index_path.is_symlink() or not index_path.is_file()):
        raise ValueError("session index must be a regular file")

    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    index_fd = os.open(index_path, flags, 0o644)
    if not stat.S_ISREG(os.fstat(index_fd).st_mode):
        os.close(index_fd)
        raise ValueError("session index must be a regular file")
    with os.fdopen(index_fd, "a+", encoding="utf-8", newline="") as index_file:
        fcntl.flock(index_file.fileno(), fcntl.LOCK_EX)
        try:
            index_file.seek(0)
            index_text = index_file.read()
            rows = parse_index(index_text, strict=True)
            inspection = inspect_rows(rows, docs_dir, thread_id, requested_mode)
            if (
                expected_previous is not None
                and expected_previous != inspection.previous
            ):
                raise RuntimeError(
                    "session state changed after inspection: "
                    f"expected previous={expected_previous}, actual={inspection.previous}"
                )

            actual_mode = inspection.recommended_mode
            save_seq = inspection.next_save_seq
            marker = (
                f"session: thread_id={thread_id} save_seq={save_seq} "
                f"mode={actual_mode} previous={inspection.previous}"
            )
            content, summary = prepare_body(body, marker)
            output_path = write_log_exclusive(docs_dir, timestamp, slug, content)
            relative_path = output_path.relative_to(docs_dir).as_posix()
            row = format_index_row(
                thread_id=thread_id,
                save_seq=save_seq,
                mode=actual_mode,
                timestamp=timestamp,
                slug=slug,
                relative_path=relative_path,
                summary=summary,
            )

            try:
                if output_path.read_text(encoding="utf-8") != content:
                    raise OSError("session log read-back did not match written content")
                append_index_locked(index_file, index_text, row)
            except BaseException as publish_error:
                rollback_file(output_path, publish_error)
                raise

            return {
                "path": str(output_path),
                "index_path": str(index_path),
                "thread_id": thread_id,
                "save_seq": save_seq,
                "mode": actual_mode,
                "previous": inspection.previous,
                "reason": inspection.reason,
            }
        finally:
            fcntl.flock(index_file.fileno(), fcntl.LOCK_UN)


def print_json(value: object) -> None:
    """Print stable JSON."""
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def main() -> int:
    """Run inspection or publication."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        workspace = Path(args.workspace).expanduser().resolve()
        thread_id = resolve_thread_id(args.thread_id)
        if args.inspect:
            requested_mode = args.mode or "auto"
            docs_dir = workspace / "docs" / "sessions"
            index_text = read_index_for_inspection(docs_dir / "index.md")
            rows = parse_index(index_text, strict=True)
            print_json(asdict(inspect_rows(rows, docs_dir, thread_id, requested_mode)))
            return 0

        if not args.slug:
            raise ValueError("--slug is required when writing a session log")
        requested_mode = args.mode or "full"
        result = publish(
            workspace=workspace,
            thread_id=thread_id,
            slug=normalize_slug(args.slug),
            timestamp=resolve_timestamp(args.timestamp),
            requested_mode=requested_mode,
            expected_previous=args.expected_previous,
            body=sys.stdin.read(),
        )
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print_json(result)
    else:
        print(result["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

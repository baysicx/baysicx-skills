"""Tests for distinct-thread session checkpoint selection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SELECTOR = Path(__file__).parents[1] / "scripts" / "select_session_logs.py"
WRITER = Path(__file__).parents[2] / "session-log" / "scripts" / "create_session_log.py"


def body(label: str = "checkpoint") -> str:
    """Return a structurally valid checkpoint body."""
    opening = [f"{label} summary sentence number {number}." for number in range(1, 11)]
    sections = [
        "# Summary",
        "Summary details.",
        "## Goal",
        "Goal details.",
        "## Context",
        "Context details.",
        "## Key Decisions",
        "Decision details.",
        "## Work Performed",
        "Work details.",
        "## Files Changed",
        "None",
        "## Validation",
        "Validation details.",
        "## Open Questions / Next Steps",
        "Next step details.",
    ]
    return "\n".join([*opening, "", *sections, ""])


def write_checkpoint(
    workspace: Path,
    thread_id: str,
    timestamp: str,
    *,
    mode: str = "auto",
    previous: str = "none",
    label: str = "checkpoint",
) -> dict[str, object]:
    """Create a fixture through the real checkpoint writer."""
    environment = os.environ.copy()
    environment["CODEX_THREAD_ID"] = thread_id
    result = subprocess.run(
        [
            sys.executable,
            str(WRITER),
            "--workspace",
            str(workspace),
            "--slug",
            f"{thread_id}-checkpoint",
            "--timestamp",
            timestamp,
            "--mode",
            mode,
            "--expected-previous",
            previous,
            "--json",
        ],
        input=body(label),
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def select(workspace: Path, count: int | None = None) -> dict[str, object]:
    """Run the public selector and return its JSON object."""
    command = [sys.executable, str(SELECTOR), "--start", str(workspace)]
    if count is not None:
        command.extend(("--count", str(count)))
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def write_raw_log(
    path: Path,
    *,
    thread_id: str,
    save_seq: int,
    mode: str,
    previous: str,
) -> None:
    """Write a minimally valid log for damaged-chain fixtures."""
    body_lines = body("raw checkpoint").splitlines()
    marker = (
        f"session: thread_id={thread_id} save_seq={save_seq} "
        f"mode={mode} previous={previous}"
    )
    path.write_text(
        "\n".join([*body_lines[:10], "", marker, "", *body_lines[11:], ""]),
        encoding="utf-8",
    )


def append_row(
    index_path: Path,
    *,
    thread_id: str,
    save_seq: int,
    mode: str,
    timestamp: str,
    relative_path: str,
    summary: str = "Valid checkpoint.",
) -> None:
    """Append one canonical row to a fixture index."""
    with index_path.open("a", encoding="utf-8") as index_file:
        index_file.write(
            f"| `{thread_id}` | {save_seq} | {mode} | `{timestamp}` | `raw` | "
            f"[{relative_path}]({relative_path}) | {summary} |\n"
        )


class SessionSelectorTest(unittest.TestCase):
    """Exercise selection, chain reconstruction, and recovery diagnostics."""

    def test_default_selects_three_distinct_threads_and_rebuilds_chain(self) -> None:
        """Multiple checkpoints from one thread consume one default slot."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            write_checkpoint(workspace, "thread-b", "260101-000001")
            write_checkpoint(workspace, "thread-c", "260101-000002")
            first = write_checkpoint(workspace, "thread-a", "260101-000003")
            second = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000004",
                previous=Path(str(first["path"])).name,
            )
            write_checkpoint(
                workspace,
                "thread-a",
                "260101-000005",
                previous=Path(str(second["path"])).name,
            )
            write_checkpoint(workspace, "thread-d", "260101-000006")

            result = select(workspace)
            threads = result["threads"]
            self.assertEqual(result["requested_count"], 3)
            self.assertEqual(result["selected_count"], 3)
            self.assertEqual(
                [thread["thread_id"] for thread in threads],
                ["thread-d", "thread-a", "thread-c"],
            )
            thread_a = next(
                thread for thread in threads if thread["thread_id"] == "thread-a"
            )
            self.assertEqual(len(thread_a["chain_paths"]), 3)
            self.assertTrue(
                thread_a["chain_paths"][0].endswith("000003-thread-a-checkpoint.md")
            )

    def test_latest_full_anchor_truncates_older_chain(self) -> None:
        """A new full checkpoint is sufficient without earlier files."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = write_checkpoint(workspace, "thread-a", "260101-000001")
            second = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000002",
                previous=Path(str(first["path"])).name,
            )
            before_anchor = select(workspace, 1)
            self.assertEqual(len(before_anchor["threads"][0]["chain_paths"]), 2)

            anchor = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000003",
                mode="full",
                previous=Path(str(second["path"])).name,
            )
            after_anchor = select(workspace, 1)
            self.assertEqual(
                after_anchor["threads"][0]["chain_paths"], [anchor["path"]]
            )

    def test_missing_and_invalid_latest_threads_do_not_consume_count(self) -> None:
        """Selection continues past unusable newest threads."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            write_checkpoint(workspace, "thread-a", "260101-000001")
            write_checkpoint(workspace, "thread-b", "260101-000002")
            write_checkpoint(
                workspace,
                "thread-c",
                "260101-000003",
                label="status: invalid",
            )
            missing = write_checkpoint(workspace, "thread-d", "260101-000004")
            Path(str(missing["path"])).unlink()
            write_checkpoint(
                workspace,
                "thread-e",
                "260101-000005",
                label="status: superseded",
            )

            result = select(workspace, 2)
            self.assertEqual(
                [thread["thread_id"] for thread in result["threads"]],
                ["thread-b", "thread-a"],
            )
            skipped_threads = {item["thread_id"] for item in result["skipped"]}
            self.assertTrue(
                {"thread-c", "thread-d", "thread-e"}.issubset(skipped_threads)
            )

    def test_missing_baseline_and_marker_mismatch_are_skipped(self) -> None:
        """A damaged thread does not fall back to an older or unrelated state."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            write_checkpoint(workspace, "thread-valid", "260101-000001")
            docs_dir = workspace / "docs" / "sessions"
            index_path = docs_dir / "index.md"

            write_raw_log(
                docs_dir / "mismatch.md",
                thread_id="another-thread",
                save_seq=1,
                mode="full",
                previous="none",
            )
            append_row(
                index_path,
                thread_id="thread-mismatch",
                save_seq=1,
                mode="full",
                timestamp="260101-000002",
                relative_path="mismatch.md",
            )
            write_raw_log(
                docs_dir / "orphan.md",
                thread_id="thread-orphan",
                save_seq=2,
                mode="incremental",
                previous="missing-base.md",
            )
            append_row(
                index_path,
                thread_id="thread-orphan",
                save_seq=2,
                mode="incremental",
                timestamp="260101-000003",
                relative_path="orphan.md",
            )

            result = select(workspace, 1)
            self.assertEqual(result["threads"][0]["thread_id"], "thread-valid")
            skipped_threads = {item["thread_id"] for item in result["skipped"]}
            self.assertTrue(
                {"thread-mismatch", "thread-orphan"}.issubset(skipped_threads)
            )

    def test_path_escape_and_cycle_are_skipped(self) -> None:
        """Unsafe paths and cyclic chains cannot displace valid history."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            write_checkpoint(workspace, "thread-valid", "260101-000001")
            docs_dir = workspace / "docs" / "sessions"
            index_path = docs_dir / "index.md"
            append_row(
                index_path,
                thread_id="thread-escape",
                save_seq=1,
                mode="full",
                timestamp="260101-000002",
                relative_path="../outside.md",
            )

            write_raw_log(
                docs_dir / "cycle-1.md",
                thread_id="thread-cycle",
                save_seq=1,
                mode="incremental",
                previous="cycle-2.md",
            )
            write_raw_log(
                docs_dir / "cycle-2.md",
                thread_id="thread-cycle",
                save_seq=2,
                mode="incremental",
                previous="cycle-1.md",
            )
            append_row(
                index_path,
                thread_id="thread-cycle",
                save_seq=1,
                mode="incremental",
                timestamp="260101-000003",
                relative_path="cycle-1.md",
            )
            append_row(
                index_path,
                thread_id="thread-cycle",
                save_seq=2,
                mode="incremental",
                timestamp="260101-000004",
                relative_path="cycle-2.md",
            )

            result = select(workspace, 1)
            self.assertEqual(result["threads"][0]["thread_id"], "thread-valid")
            reasons = "\n".join(item["reason"] for item in result["skipped"])
            self.assertIn("cycle", reasons)
            self.assertIn("unsafe session path", reasons)

    def test_upward_discovery_and_workspace_fallback_do_not_scan_siblings(self) -> None:
        """Discovery stays within ancestors or the explicit fallback workspace."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            write_checkpoint(workspace, "thread-a", "260101-000001")
            child = workspace / "nested" / "child"
            child.mkdir(parents=True)
            discovered = select(child, 1)
            self.assertEqual(discovered["selected_count"], 1)

            sibling_start = root / "unrelated" / "child"
            sibling_start.mkdir(parents=True)
            absent = select(sibling_start, 1)
            self.assertIsNone(absent["index_path"])

            fallback = subprocess.run(
                [
                    sys.executable,
                    str(SELECTOR),
                    "--start",
                    str(sibling_start),
                    "--workspace",
                    str(workspace),
                    "--count",
                    "1",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(fallback.returncode, 0, fallback.stderr)
            self.assertEqual(json.loads(fallback.stdout)["selected_count"], 1)

    def test_non_positive_count_is_rejected(self) -> None:
        """N must be a positive integer."""
        result = subprocess.run(
            [sys.executable, str(SELECTOR), "--count", "0"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("positive integer", result.stderr)


if __name__ == "__main__":
    unittest.main()

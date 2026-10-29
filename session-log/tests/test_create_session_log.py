"""Tests for thread-aware session checkpoint publication."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "create_session_log.py"


def body(label: str = "checkpoint") -> str:
    """Return a structurally valid session body."""
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


def run_cli(
    workspace: Path,
    thread_id: str | None,
    *arguments: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the writer with an isolated thread environment."""
    environment = os.environ.copy()
    environment.pop("CODEX_THREAD_ID", None)
    if thread_id is not None:
        environment["CODEX_THREAD_ID"] = thread_id
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--workspace", str(workspace), *arguments],
        input=input_text,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def write_checkpoint(
    workspace: Path,
    thread_id: str,
    timestamp: str,
    *,
    mode: str = "auto",
    previous: str = "none",
    label: str = "checkpoint",
) -> dict[str, object]:
    """Write a checkpoint and return its JSON result."""
    result = run_cli(
        workspace,
        thread_id,
        "--slug",
        "test-checkpoint",
        "--timestamp",
        timestamp,
        "--mode",
        mode,
        "--expected-previous",
        previous,
        "--json",
        input_text=body(label),
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class SessionLogCliTest(unittest.TestCase):
    """Exercise public writer and inspection behavior."""

    def test_auto_rotation_preserves_full_and_incremental_files(self) -> None:
        """Auto mode rotates full, incremental, incremental, full."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = write_checkpoint(workspace, "thread-a", "260101-000001")
            second = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000002",
                previous=Path(str(first["path"])).name,
            )
            third = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000003",
                previous=Path(str(second["path"])).name,
            )

            inspection = run_cli(workspace, "thread-a", "--inspect", "--mode", "auto")
            self.assertEqual(inspection.returncode, 0, inspection.stderr)
            recommendation = json.loads(inspection.stdout)
            self.assertEqual(recommendation["recommended_mode"], "full")
            self.assertEqual(recommendation["consecutive_incrementals"], 2)

            fourth = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000004",
                previous=Path(str(third["path"])).name,
            )
            self.assertEqual(
                [first["mode"], second["mode"], third["mode"], fourth["mode"]],
                ["full", "incremental", "incremental", "full"],
            )
            self.assertEqual([first["save_seq"], fourth["save_seq"]], [1, 4])
            for result in (first, second, third, fourth):
                self.assertTrue(Path(str(result["path"])).is_file())

    def test_incremental_without_baseline_degrades_and_legacy_write_is_full(
        self,
    ) -> None:
        """Unsafe incremental requests and mode-less calls both store full logs."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000001",
                mode="incremental",
            )
            self.assertEqual(first["mode"], "full")
            self.assertIn("no previous checkpoint", str(first["reason"]))

            second = run_cli(
                workspace,
                "thread-a",
                "--slug",
                "legacy-call",
                "--timestamp",
                "260101-000002",
                "--json",
                input_text=body("legacy"),
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["mode"], "full")

    def test_explicit_full_creates_anchor(self) -> None:
        """Explicit full overrides an otherwise available incremental."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = write_checkpoint(workspace, "thread-a", "260101-000001")
            second = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000002",
                mode="full",
                previous=Path(str(first["path"])).name,
            )
            self.assertEqual(second["mode"], "full")
            self.assertEqual(second["save_seq"], 2)

    def test_invalid_body_and_missing_thread_id_write_nothing(self) -> None:
        """Input validation occurs before workspace mutation."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            malformed = run_cli(
                workspace,
                "thread-a",
                "--slug",
                "bad-body",
                input_text="too short\n",
            )
            self.assertNotEqual(malformed.returncode, 0)
            self.assertFalse((workspace / "docs").exists())

            missing_thread = run_cli(
                workspace,
                None,
                "--slug",
                "missing-thread",
                input_text=body(),
            )
            self.assertNotEqual(missing_thread.returncode, 0)
            self.assertIn("thread ID is required", missing_thread.stderr)
            self.assertFalse((workspace / "docs").exists())

            explicit_thread = run_cli(
                workspace,
                None,
                "--thread-id",
                "explicit-test-thread",
                "--inspect",
            )
            self.assertEqual(explicit_thread.returncode, 0, explicit_thread.stderr)
            self.assertEqual(
                json.loads(explicit_thread.stdout)["thread_id"],
                "explicit-test-thread",
            )

    def test_filename_collision_uses_suffix_without_overwrite(self) -> None:
        """The same timestamp and slug never replace an earlier file."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000001",
                mode="full",
                label="first",
            )
            first_content = Path(str(first["path"])).read_text(encoding="utf-8")
            second = write_checkpoint(
                workspace,
                "thread-b",
                "260101-000001",
                mode="full",
                label="second",
            )
            self.assertNotEqual(first["path"], second["path"])
            self.assertTrue(str(second["path"]).endswith("-2.md"))
            self.assertEqual(
                Path(str(first["path"])).read_text(encoding="utf-8"), first_content
            )

    def test_same_predecessor_concurrency_allows_one_success(self) -> None:
        """Only one competing incremental can commit from one predecessor."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            first = write_checkpoint(workspace, "thread-a", "260101-000001")
            previous = Path(str(first["path"])).name
            environment = os.environ.copy()
            environment["CODEX_THREAD_ID"] = "thread-a"
            commands = []
            for number in (2, 3):
                commands.append(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--workspace",
                        str(workspace),
                        "--slug",
                        f"concurrent-{number}",
                        "--timestamp",
                        f"260101-00000{number}",
                        "--mode",
                        "incremental",
                        "--expected-previous",
                        previous,
                        "--json",
                    ]
                )
            processes = [
                subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=environment,
                )
                for command in commands
            ]
            outcomes = [
                process.communicate(body("concurrent")) for process in processes
            ]
            codes = [process.returncode for process in processes]
            self.assertEqual(sorted(codes), [0, 1], outcomes)

            successful_stdout = outcomes[codes.index(0)][0]
            winner = json.loads(successful_stdout)
            retry = write_checkpoint(
                workspace,
                "thread-a",
                "260101-000004",
                previous=Path(str(winner["path"])).name,
            )
            self.assertEqual(retry["save_seq"], 3)

            index_lines = (workspace / "docs" / "sessions" / "index.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(index_lines.count("| `thread-a` |"), 3)
            self.assertEqual(
                len(list((workspace / "docs" / "sessions").glob("*.md"))), 4
            )


class SessionLogTransactionTest(unittest.TestCase):
    """Exercise failure rollback within the writer transaction."""

    @staticmethod
    def load_module() -> object:
        """Load the writer module without relying on package installation."""
        spec = importlib.util.spec_from_file_location(
            "session_log_writer_tested", SCRIPT
        )
        if spec is None or spec.loader is None:
            raise AssertionError("could not load writer module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_index_fsync_failure_rolls_back_partial_index_and_log(self) -> None:
        """A failed index append restores its old length and removes the new log."""
        module = self.load_module()
        real_fsync = os.fsync
        calls = 0

        def fail_second_fsync(file_descriptor: int) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected index failure")
            real_fsync(file_descriptor)

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            with mock.patch.object(module.os, "fsync", side_effect=fail_second_fsync):
                with self.assertRaises(OSError):
                    module.publish(
                        workspace=workspace,
                        thread_id="thread-a",
                        slug="rollback-test",
                        timestamp="260101-000001",
                        requested_mode="full",
                        expected_previous="none",
                        body=body(),
                    )

            docs_dir = workspace / "docs" / "sessions"
            self.assertEqual(list(docs_dir.glob("*.md")), [docs_dir / "index.md"])
            self.assertEqual((docs_dir / "index.md").read_text(encoding="utf-8"), "")

            retry = module.publish(
                workspace=workspace,
                thread_id="thread-a",
                slug="rollback-test",
                timestamp="260101-000002",
                requested_mode="full",
                expected_previous="none",
                body=body(),
            )
            self.assertEqual(retry["save_seq"], 1)


if __name__ == "__main__":
    unittest.main()

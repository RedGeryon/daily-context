from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "bin" / "daily-context"


class DailyContextCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "project"
        self.context = self.workspace / "daily_context"
        self.workspace.mkdir()

    def run_cli(self, *args: str, input_value: dict | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(CLI), *args],
            cwd=self.workspace,
            input=json.dumps(input_value) if input_value is not None else None,
            text=True,
            capture_output=True,
            check=True,
        )

    def init(self, auto: str = "off") -> None:
        self.run_cli(
            "init", str(self.context), "--workspace", str(self.workspace),
            "--date", "2026-08-26", "--goal", "Ship a traceable work record",
            "--workstream", "Core product",
            "--auto-update", auto,
        )

    def test_full_daily_and_weekly_flow(self) -> None:
        self.init()
        source = self.workspace / "meeting.md"
        source.write_text("Alex said the launch is Friday.\n", encoding="utf-8")
        source_id = self.run_cli(
            "add-source", str(source), "--context", str(self.context),
            "--kind", "meeting", "--title", "Launch review", "--date", "2026-08-26",
        ).stdout.strip()
        self.assertEqual(source_id, "SRC-2026-08-26-001")

        task_id = self.run_cli(
            "record", "task", "Confirm the launch date", "--context", str(self.context),
            "--status", "open", "--sources", source_id, "--date", "2026-08-26",
        ).stdout.strip()
        self.assertEqual(task_id, "TASK-2026-08-26-001")
        self.run_cli("set-status", task_id, "done", "--context", str(self.context), "--date", "2026-08-26")
        self.run_cli("validate", "--context", str(self.context))
        trace = self.run_cli("trace", task_id, "--context", str(self.context)).stdout
        self.assertIn(source_id, trace)

        status = json.loads(self.run_cli("status", "--context", str(self.context)).stdout)
        self.assertEqual(status["active_tasks"], 0)
        self.assertEqual(status["active_goals"], 1)
        self.run_cli("weekly", "--context", str(self.context), "--week", "2026-W35")
        manifest = json.loads((self.context / "weeks/2026-W35/source-manifest.json").read_text())
        self.assertIn(task_id, manifest["record_ids"])
        self.assertTrue((self.context / "days/2026/08/2026-08-26/raw").is_dir())
        self.assertIn("Core product", (self.context / "PROFILE.md").read_text())
        self.assertIn("days/**/raw/", (self.context / ".gitignore").read_text())
        ledger = (self.context / "days/2026/08/2026-08-26/records.ndjson").read_text()
        self.assertNotIn(str(source), ledger)
        local_locations = json.loads((self.context / ".source-locations.local.json").read_text())
        self.assertEqual(local_locations[source_id], str(source.resolve()))

    def test_auto_capture_is_private_pending_and_deduplicated(self) -> None:
        self.init(auto="capture")
        transcript = self.workspace / "session.jsonl"
        transcript.write_text('{"role":"user","text":"private"}\n', encoding="utf-8")
        payload = {
            "session_id": "session-123",
            "cwd": str(self.workspace),
            "transcript_path": str(transcript),
            "reason": "exit",
        }
        first = self.run_cli(
            "capture-session", "--host", "codex", "--context", str(self.context), input_value=payload
        )
        second = self.run_cli(
            "capture-session", "--host", "codex", "--context", str(self.context), input_value=payload
        )
        self.assertEqual(first.stdout.strip(), "SRC-2026-08-26-001")
        self.assertEqual(second.stdout.strip(), "")
        status = json.loads(self.run_cli("status", "--context", str(self.context)).stdout)
        self.assertEqual(status["pending_sources"], 1)
        raw_files = list((self.context / "days/2026/08/2026-08-26/raw").iterdir())
        self.assertEqual(len(raw_files), 2)
        self.run_cli("set-status", first.stdout.strip(), "verified", "--context", str(self.context))
        reviewed = json.loads(self.run_cli("status", "--context", str(self.context)).stdout)
        self.assertEqual(reviewed["pending_sources"], 0)

    def test_auto_enable_preserves_host_settings_and_is_idempotent(self) -> None:
        self.init()
        codex = self.workspace / ".codex"
        codex.mkdir()
        (codex / "hooks.json").write_text(json.dumps({"unrelated": {"keep": True}}), encoding="utf-8")
        self.run_cli(
            "auto", "enable", "--host", "codex", "--workspace", str(self.workspace),
            "--context", str(self.context),
        )
        self.run_cli(
            "auto", "enable", "--host", "codex", "--workspace", str(self.workspace),
            "--context", str(self.context),
        )
        settings = json.loads((codex / "hooks.json").read_text())
        self.assertTrue(settings["unrelated"]["keep"])
        self.assertEqual(len(settings["hooks"]["SessionEnd"]), 1)
        command = settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"]
        self.assertNotIn(str(self.context), command)
        self.assertTrue((codex / "hooks.json.bak").exists())

    def test_validate_rejects_missing_source(self) -> None:
        self.init()
        self.run_cli(
            "record", "fact", "Unsupported claim", "--status", "reported",
            "--sources", "SRC-2026-08-26-999", "--date", "2026-08-26",
            "--context", str(self.context),
        )
        result = subprocess.run(
            [str(CLI), "validate", "--context", str(self.context)],
            cwd=self.workspace, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing source", result.stderr)

    def test_init_without_goal_still_has_a_day_index(self) -> None:
        self.run_cli("init", str(self.context), "--workspace", str(self.workspace), "--date", "2026-08-26")
        self.assertTrue((self.context / "days/2026/08/2026-08-26/INDEX.md").exists())
        self.assertIn("2026-08-26", (self.context / "CONTEXT.md").read_text())


if __name__ == "__main__":
    unittest.main()

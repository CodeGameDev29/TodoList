from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("qa_harness", ROOT / "qa/harness.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
validator_spec = importlib.util.spec_from_file_location(
    "harness_validator", ROOT / "scripts/harness/validate_harness.py"
)
validator = importlib.util.module_from_spec(validator_spec)
validator_spec.loader.exec_module(validator)
sync_spec = importlib.util.spec_from_file_location(
    "harness_sync", ROOT / "scripts/harness/sync_agent_harness.py"
)
sync = importlib.util.module_from_spec(sync_spec)
sync_spec.loader.exec_module(sync)


class CodeReviewerPolicyTests(unittest.TestCase):
    def reviewer(self):
        source = ROOT / ".claude/agents/code-reviewer.md"
        meta, _ = sync.parse_frontmatter(source)
        name, generated = sync.role_toml(source)
        self.assertEqual(name, "code-reviewer")
        return meta, tomllib.loads(generated)

    def test_reviewer_is_registered_read_only_high_effort_and_rubric_based(self):
        self.assertIn("code-reviewer", validator.ROLES)
        self.assertIn("code-reviewer", validator.READ_ONLY)
        self.assertIn("code-reviewer", sync.READ_ONLY)
        meta, generated = self.reviewer()
        self.assertEqual(generated["sandbox_mode"], "read-only")
        self.assertEqual(generated["model_reasoning_effort"], "high")
        validator.check_role("code-reviewer", meta, generated)

    def test_reviewer_rejects_write_access_low_effort_and_missing_rubric(self):
        for field, value in (
            ("sandbox_mode", "workspace-write"),
            ("model_reasoning_effort", "medium"),
            ("developer_instructions", "Review code."),
        ):
            with self.subTest(field=field):
                meta, generated = self.reviewer()
                generated[field] = value
                with self.assertRaises(SystemExit):
                    validator.check_role("code-reviewer", meta, generated)
        meta, generated = self.reviewer()
        meta["tools"] = "Read, Glob, Grep, Write"
        with self.assertRaisesRegex(SystemExit, "independence policy"):
            validator.check_role("code-reviewer", meta, generated)

    def test_reviewer_rejects_matching_medium_effort(self):
        meta, generated = self.reviewer()
        meta["effort"] = "medium"
        generated["model_reasoning_effort"] = "medium"
        with self.assertRaisesRegex(SystemExit, "independence policy"):
            validator.check_role("code-reviewer", meta, generated)


class HarnessApplicationTransitionTests(unittest.TestCase):
    def test_optional_recorded_report_ids_validation(self):
        registry = {"schema_version": 1, "classes": []}
        ledger = {"schema_version": 2, "classes": {}}
        validator.check_qa_state(registry, ledger)
        ledger["recorded_report_ids"] = ["report-1", "report_2"]
        validator.check_qa_state(registry, ledger)
        for identifiers in (
            ["report-1", "report-1"],
            ["../unsafe"],
            ["CON"],
            "report-1",
            None,
        ):
            with self.subTest(identifiers=identifiers):
                ledger["recorded_report_ids"] = identifiers
                with self.assertRaises(SystemExit):
                    validator.check_qa_state(registry, ledger)

    def test_scan_excludes_dependencies_and_runtime_but_keeps_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            (root / ".gitignore").write_text(
                "node_modules/\n.qa-artifacts/\n.playwright-mcp/\n"
            )
            for directory in (
                "node_modules",
                ".qa-artifacts",
                ".playwright-mcp/traces",
                "apps/api",
            ):
                (root / directory).mkdir(parents=True)
            for filename in (
                "node_modules/package.json",
                ".qa-artifacts/run.log",
                ".playwright-mcp/traces/runtime.trace",
                "apps/api/source.js",
                "package.json",
            ):
                (root / filename).write_text("sample")
            files = {
                path.relative_to(root).as_posix()
                for path in validator.source_files(root)
            }
            self.assertEqual(
                files, {".gitignore", "apps/api/source.js", "package.json"}
            )

    def test_populated_qa_state_is_valid_and_unknown_class_is_rejected(self):
        registry = {
            "schema_version": 1,
            "classes": [
                {
                    "schema_version": 1,
                    "id": "C1",
                    "title": "Failure",
                    "regression_rows": [{"id": "one"}],
                }
            ],
        }
        entry = {
            "state": "open",
            "events": [],
            "regression_rows": {"one": "UNRUN"},
            "clean_rounds": 0,
            "process_failure": False,
            "last_shipped_change": None,
        }
        validator.check_qa_state(
            registry, {"schema_version": 2, "classes": {"C1": entry}}
        )
        with self.assertRaises(SystemExit):
            validator.check_qa_state(
                registry, {"schema_version": 2, "classes": {"unknown": entry}}
            )
        entry["regression_rows"]["one"] = "MAYBE"
        with self.assertRaises(SystemExit):
            validator.check_qa_state(
                registry, {"schema_version": 2, "classes": {"C1": entry}}
            )


class CodexSemanticValidationTests(unittest.TestCase):
    def test_version_probe_timeout_is_a_contextual_failure(self):
        with (
            patch.object(validator.shutil, "which", return_value="codex"),
            patch.object(
                validator.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["codex", "--version"], 30),
            ) as run,
        ):
            with self.assertRaisesRegex(SystemExit, "Codex version probe timed out"):
                validator.semantic_codex()
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_version_probe_nonzero_exit_preserves_diagnostics(self):
        result = subprocess.CompletedProcess(
            ["codex", "--version"],
            1,
            stdout="codex 0.160.1",
            stderr="version launcher failed",
        )
        with (
            patch.object(validator.shutil, "which", return_value="codex"),
            patch.object(validator.subprocess, "run", return_value=result),
            patch.object(validator, "isolated_codex_environment") as isolated,
        ):
            with self.assertRaises(SystemExit) as failure:
                validator.semantic_codex()
        self.assertIn("Codex version probe failed", str(failure.exception))
        self.assertIn("stdout: codex 0.160.1", str(failure.exception))
        self.assertIn("stderr: version launcher failed", str(failure.exception))
        isolated.assert_not_called()

    def test_successful_version_probe_is_bounded_and_runs_semantic_checks(self):
        result = subprocess.CompletedProcess(
            ["codex", "--version"], 0, stdout="codex 0.160.1", stderr=""
        )
        with (
            patch.object(validator.shutil, "which", return_value="codex"),
            patch.object(validator.subprocess, "run", return_value=result) as run,
            patch.object(validator, "isolated_codex_environment") as isolated,
            patch.object(validator, "run_semantic_command") as semantic,
        ):
            isolated.return_value.__enter__.return_value = {}
            validator.semantic_codex()
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertEqual(semantic.call_count, 2)
        self.assertEqual(
            semantic.call_args_list[0].args,
            (["codex", "app-server", "--strict-config", "--stdio"], {}),
        )
        self.assertEqual(
            semantic.call_args_list[1].args,
            (["codex", "debug", "prompt-input", "x"], {}),
        )

    def test_isolated_home_stays_in_workspace_and_has_no_credentials(self):
        original_config = (ROOT / ".codex/config.toml").read_bytes()
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            shutil.copytree(
                ROOT / ".codex", root / ".codex", ignore=shutil.ignore_patterns("tmp")
            )
            with (
                patch.object(validator, "ROOT", root),
                patch.object(
                    validator.Path,
                    "home",
                    side_effect=AssertionError("User home must not be used"),
                ),
                patch.dict(
                    os.environ,
                    {"OPENAI_API_KEY": "test-only", "CODEX_API_KEY": "test-only"},
                ),
            ):
                with validator.isolated_codex_environment() as environment:
                    home = Path(environment["CODEX_HOME"])
                    self.assertEqual(
                        home.parent, root / ".qa-artifacts/harness-validation"
                    )
                    self.assertNotIn("OPENAI_API_KEY", environment)
                    self.assertNotIn("CODEX_API_KEY", environment)
                    self.assertFalse((home / "auth.json").exists())
                    self.assertEqual(
                        tomllib.loads((home / "config.toml").read_text())["projects"][
                            str(root)
                        ]["trust_level"],
                        "trusted",
                    )
                self.assertFalse(home.exists())
        self.assertEqual((ROOT / ".codex/config.toml").read_bytes(), original_config)

    def test_cleanup_retries_a_transient_directory_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            home = parent / "owned-fixture"
            home.mkdir()
            remove = shutil.rmtree
            attempts = []

            def locked_once(path):
                attempts.append(path)
                if len(attempts) == 1:
                    raise PermissionError("directory still in use")
                remove(path)

            with patch.object(validator.shutil, "rmtree", side_effect=locked_once):
                validator.cleanup_codex_home(home, parent)
            self.assertFalse(home.exists())
            self.assertEqual(len(attempts), 2)

    def test_cleanup_failure_is_bounded_and_identifies_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            home = parent / "owned-fixture"
            home.mkdir()
            with patch.object(
                validator.shutil, "rmtree", side_effect=PermissionError("still locked")
            ) as remove:
                with self.assertRaisesRegex(SystemExit, "cleanup failed") as error:
                    validator.cleanup_codex_home(home, parent)
            self.assertIn(str(home), str(error.exception))
            self.assertLessEqual(remove.call_count, 5)
            self.assertTrue(home.exists())

    def test_cleanup_refuses_parent_or_outside_path(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            with patch.object(validator.shutil, "rmtree") as remove:
                for home in (parent, parent.parent / "unrelated"):
                    with (
                        self.subTest(home=home),
                        self.assertRaisesRegex(SystemExit, "outside"),
                    ):
                        validator.cleanup_codex_home(home, parent)
                remove.assert_not_called()

    def test_real_cli_accepts_valid_config_without_credentials_and_rejects_unknown_field(
        self,
    ):
        codex = shutil.which("codex")
        self.assertIsNotNone(
            codex, "Pinned Codex is required for semantic regression coverage"
        )
        validator.semantic_codex()
        with validator.isolated_codex_environment() as environment:
            config = Path(environment["CODEX_HOME"]) / "config.toml"
            config.write_text(
                "unsupported_field_for_regression = true\n" + config.read_text()
            )
            with self.assertRaisesRegex(
                SystemExit,
                "unknown configuration field.*unsupported_field_for_regression",
            ):
                validator.run_semantic_command(
                    [codex, "app-server", "--strict-config", "--stdio"], environment
                )

    def test_semantic_failure_preserves_both_diagnostic_streams(self):
        result = subprocess.CompletedProcess(
            ["codex", "command"], 1, stdout="actual failure", stderr="helper warning"
        )
        with patch.object(validator.subprocess, "run", return_value=result) as run:
            with self.assertRaises(SystemExit) as failure:
                validator.run_semantic_command(["codex", "command"], {})
        self.assertIn("stdout: actual failure", str(failure.exception))
        self.assertIn("stderr: helper warning", str(failure.exception))
        self.assertEqual(run.call_args.kwargs["input"], "")
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_semantic_timeout_is_a_hard_failure(self):
        with patch.object(
            validator.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["codex"], 30),
        ):
            with self.assertRaisesRegex(SystemExit, "timed out"):
                validator.run_semantic_command(["codex", "command"], {})


class QAHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = qa.QA, qa.ART, qa.STATE
        self.report_sequence = 0
        qa.QA, qa.ART, qa.STATE = (
            self.root / "qa",
            self.root / "artifacts",
            self.root / "state",
        )
        (qa.QA / "journeys").mkdir(parents=True)
        qa.ART.mkdir()
        qa.STATE.mkdir()
        qa.save(qa.STATE / "bug-classes.json", {"schema_version": 1, "classes": []})
        qa.save(qa.STATE / "ledger.json", {"schema_version": 2, "classes": {}})
        self.journey = {
            "schema_version": 1,
            "id": "journey",
            "title": "Example",
            "kind": "ui-only",
            "base_url_env": "TODO_URL",
            "steps": [
                {
                    "id": "one",
                    "expectation": "visible",
                    "tdd_expect": "PASS",
                    "actions": [{"type": "navigate", "url": "/"}],
                }
            ],
        }
        qa.save(qa.QA / "journeys/journey.json", self.journey)
        for name in ("shot.png", "trace.zip", "console.log", "network.json"):
            (qa.ART / name).write_text("evidence")

    def tearDown(self):
        qa.QA, qa.ART, qa.STATE = self.old
        self.tmp.cleanup()

    def report(self, result="FAIL", class_id="C1", change="change-a", run_id=None):
        self.report_sequence += 1
        evidence = {
            key: str(qa.ART / name)
            for key, name in {
                "screenshot": "shot.png",
                "trace": "trace.zip",
                "console": "console.log",
                "network": "network.json",
            }.items()
        }
        return {
            "schema_version": 1,
            "id": run_id or f"r-{result}-{change}-{self.report_sequence}",
            "journey_id": "journey",
            "phase": "red" if result == "FAIL" else "green",
            "complete": True,
            "run_valid": True,
            "runner": {"identity": "runner"},
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:00:01Z",
            "browser": {"headed": True, "foreground": True, "title": "TodoList"},
            "wall_clock_ms": 1000,
            "steps": [{"id": "one", "result": result, "evidence": evidence}],
            "judge": {
                "identity": "judge",
                "verdict": result,
                "rows": [{"step_id": "one", "verdict": result, "class_id": class_id}],
            },
            "change_id": change,
        }

    def add_class(self):
        qa.save(
            qa.STATE / "bug-classes.json",
            {
                "schema_version": 1,
                "classes": [
                    {
                        "schema_version": 1,
                        "id": "C1",
                        "title": "Class one",
                        "regression_rows": [{"id": "one"}],
                    }
                ],
            },
        )

    def test_positive_journey_preflight(self):
        self.assertIsNone(qa.validate_journey(self.journey))

    def test_headless_and_network_bypass_refused(self):
        bad = json.loads(json.dumps(self.journey))
        bad["steps"][0]["headless"] = True
        self.assertIn("headless", qa.validate_journey(bad))
        bad = json.loads(json.dumps(self.journey))
        bad["steps"][0]["actions"] = [{"type": "fetch", "url": "/"}]
        self.assertIn("allowed UI", qa.validate_journey(bad))

    def test_valid_report_and_missing_evidence(self):
        self.add_class()
        report = self.report()
        self.assertIsNone(qa.validate_report(report))
        report["steps"][0]["evidence"]["screenshot"] = str(self.root / "outside.png")
        self.assertIn("screenshot", qa.validate_report(report))

    def test_runner_judge_and_third_verdict_refusals(self):
        self.add_class()
        report = self.report()
        report["judge"]["identity"] = "runner"
        self.assertIn("independent", qa.validate_report(report))
        report = self.report()
        report["judge"]["verdict"] = "MAYBE"
        self.assertIn("verdict", qa.validate_report(report))

    def test_missing_extra_rows_and_unknown_class(self):
        self.add_class()
        report = self.report()
        report["judge"]["rows"] = []
        self.assertIn("cover every", qa.validate_report(report))
        report = self.report(class_id="unknown")
        self.assertIn("unknown class", qa.validate_report(report))

    def test_proposed_class_and_invalid_run_refusal(self):
        report = self.report()
        report["judge"]["rows"][0].pop("class_id")
        report["judge"]["rows"][0]["proposed_class_id"] = "C1"
        report["proposed_classes"] = [
            {
                "schema_version": 1,
                "id": "C1",
                "title": "Class one",
                "regression_rows": [{"id": "one"}],
            }
        ]
        self.assertIsNone(qa.validate_report(report))
        report["run_valid"] = False
        with self.assertRaises(ValueError):
            qa.record(report)

    def test_per_class_red_green_regression_and_closure(self):
        self.add_class()
        qa.record(self.report("FAIL", change="same", run_id="red-1"))
        qa.record(self.report("FAIL", change="same", run_id="red-2"))
        entry = qa.load(qa.STATE / "ledger.json")["classes"]["C1"]
        self.assertTrue(entry["process_failure"])
        self.assertEqual(entry["state"], "open")
        qa.record(self.report("PASS", change="fix"))
        qa.record(self.report("PASS", change="fix2"))
        self.assertEqual(
            qa.load(qa.STATE / "ledger.json")["classes"]["C1"]["state"], "closed"
        )
        qa.record(self.report("FAIL", change="regression"))
        self.assertEqual(
            qa.load(qa.STATE / "ledger.json")["classes"]["C1"]["state"], "open"
        )

    def test_duplicate_report_rejected_before_registry_or_ledger_mutation(self):
        self.add_class()
        report = self.report("PASS", run_id="green-1")
        qa.record(report)
        before = {
            name: (qa.STATE / name).read_bytes()
            for name in ("ledger.json", "bug-classes.json")
        }
        report["proposed_classes"] = [
            {
                "schema_version": 1,
                "id": "C2",
                "title": "Another class",
                "regression_rows": [{"id": "one"}],
            }
        ]
        with self.assertRaisesRegex(ValueError, "already recorded"):
            qa.record(report)
        for name, contents in before.items():
            self.assertEqual((qa.STATE / name).read_bytes(), contents)
        entry = qa.load(qa.STATE / "ledger.json")["classes"]["C1"]
        self.assertEqual(entry["clean_rounds"], 1)
        self.assertEqual(entry["state"], "open")

    def test_duplicate_report_without_class_rows_is_rejected(self):
        report = self.report("PASS", class_id=None, run_id="unclassified-1")
        qa.record(report)
        before = (qa.STATE / "ledger.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already recorded"):
            qa.record(report)
        self.assertEqual((qa.STATE / "ledger.json").read_bytes(), before)

    def test_historical_event_id_is_rejected_without_tracking_list(self):
        self.add_class()
        report = self.report(run_id="historical-1")
        qa.record(report)
        ledger = qa.load(qa.STATE / "ledger.json")
        ledger.pop("recorded_report_ids", None)
        qa.save(qa.STATE / "ledger.json", ledger)
        before = (qa.STATE / "ledger.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already recorded"):
            qa.record(report)
        self.assertEqual((qa.STATE / "ledger.json").read_bytes(), before)
        self.assertFalse(ledger["classes"]["C1"]["process_failure"])

    def test_unsafe_report_ids_are_rejected_in_paths_and_stored_reports(self):
        self.add_class()
        for report_id in (
            "",
            "../escape",
            "a/b",
            r"a\b",
            "/absolute",
            r"C:\absolute",
            "a:stream",
            ".",
            "..",
            "CON",
            "con",
            "NUL",
            "AUX",
            "PRN",
            "COM1",
            "LPT9",
            "CON.txt",
            "trailing.",
            "two words",
            "café",
        ):
            with self.subTest(report_id=report_id):
                with self.assertRaisesRegex(ValueError, "report ID"):
                    qa.report_path(report_id)
                report = self.report()
                report["id"] = report_id
                self.assertIn("report ID", qa.validate_report(report))

    def test_unsafe_cli_ids_fail_with_clear_diagnostics(self):
        for command in ("new-report", "judge-pack", "intake", "record"):
            with self.subTest(command=command):
                with patch.object(sys, "argv", ["qa", command, "../escape"]):
                    with self.assertRaisesRegex(SystemExit, "report ID"):
                        qa.main()
        self.assertFalse((qa.ART / "escape.json").exists())

    def test_report_and_judge_pack_symlinks_cannot_escape_artifact_directories(self):
        self.add_class()
        report = self.report(run_id="safe")
        outside = self.root / "outside.json"
        qa.save(outside, report)
        for folder in ("reports", "judge-packs"):
            (qa.ART / folder).mkdir()
        qa.save(qa.ART / "reports/safe.json", report)
        try:
            (qa.ART / "reports/escape.json").symlink_to(outside)
            (qa.ART / "judge-packs/safe.json").symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Host cannot create symlinks: {exc}")
        with self.assertRaisesRegex(ValueError, "outside"):
            qa.report_path("escape")
        before = outside.read_bytes()
        with patch.object(sys, "argv", ["qa", "judge-pack", "safe"]):
            with self.assertRaisesRegex(SystemExit, "outside"):
                qa.main()
        self.assertEqual(outside.read_bytes(), before)

    def test_resolved_report_paths_cannot_escape_even_without_symlink_privileges(self):
        original_resolve = Path.resolve
        for redirected in (qa.ART / "reports", qa.ART / "reports/escape.json"):
            with self.subTest(redirected=redirected):

                def resolve(path, *args, **kwargs):
                    if path == redirected:
                        return self.root / "outside"
                    return original_resolve(path, *args, **kwargs)

                with patch.object(qa.Path, "resolve", resolve):
                    with self.assertRaisesRegex(ValueError, "outside"):
                        qa.report_path("escape")

    def test_invalid_timing_is_rejected(self):
        self.add_class()
        cases = (
            ("started_at", "not-a-date"),
            ("started_at", "2026-01-01T00:00:00"),
            ("started_at", None),
            ("started_at", 1000),
            ("finished_at", "2025-12-31T23:59:59Z"),
            ("finished_at", ""),
            ("finished_at", "2026-01-01T00:00:01"),
            ("wall_clock_ms", -1),
            ("wall_clock_ms", True),
            ("wall_clock_ms", False),
            ("wall_clock_ms", float("nan")),
            ("wall_clock_ms", float("inf")),
            ("wall_clock_ms", float("-inf")),
            ("wall_clock_ms", "1000"),
            ("wall_clock_ms", None),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                report = self.report()
                report[field] = value
                self.assertIsNotNone(qa.validate_report(report))

    def test_valid_timing_accepts_offsets_equal_instants_and_fractional_duration(self):
        self.add_class()
        report = self.report()
        report["started_at"] = "2026-01-01T01:00:00+01:00"
        report["finished_at"] = "2026-01-01T00:00:00Z"
        for duration in (0, 0.5, 1000):
            report["wall_clock_ms"] = duration
            self.assertIsNone(qa.validate_report(report))


class HarnessConfigTests(unittest.TestCase):
    def test_sync_config_roles_hooks_and_pins(self):
        self.assertEqual(
            subprocess.run(
                [sys.executable, "scripts/harness/sync_agent_harness.py", "--check"],
                cwd=ROOT,
            ).returncode,
            0,
        )
        self.assertEqual(
            subprocess.run(
                [sys.executable, "scripts/harness/validate_harness.py"], cwd=ROOT
            ).returncode,
            0,
        )
        self.assertIn("@playwright/mcp@0.0.83", (ROOT / ".mcp.json").read_text())
        self.assertIn(
            "model_reasoning_effort", (ROOT / ".codex/agents/verifier.toml").read_text()
        )

    def test_claude_settings_exact_shape(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        self.assertEqual(
            settings["modelSettings"],
            {
                "claude-fable-5-1": {"effortLevel": "high", "maxEffortLevel": "xhigh"},
                "claude-opus-5-5": {"effortLevel": "medium", "maxEffortLevel": "high"},
            },
        )
        self.assertEqual(
            settings["env"],
            {
                "CLAUDE_CODE_SUBAGENT_MODEL": "claude-opus-5-5",
                "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1",
                "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "4",
                "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "2",
            },
        )
        self.assertFalse(
            {
                "orchestrator",
                "agents",
                "reasoningEffort",
                "mcpServers",
                "crossSessionInbound",
            }
            & settings.keys()
        )
        for rows in settings["hooks"].values():
            for row in rows:
                for hook in row["hooks"]:
                    self.assertNotIn("commandWindows", hook)
                    self.assertTrue(
                        hook["command"].startswith(
                            'sh "$CLAUDE_PROJECT_DIR/.claude/hooks/py.sh"'
                        )
                    )

    def test_claude_hooks_run_from_nested_directory(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("POSIX sh (Git Bash) is unavailable on this Windows host")
        environment = os.environ.copy()
        environment["CLAUDE_PROJECT_DIR"] = str(ROOT)
        nested = ROOT / "apps/web"
        for script in (
            "session_start.py",
            "project_rules_reminder.py",
            "output_meter.py",
            "completion_referee.py",
        ):
            result = subprocess.run(
                [
                    shell,
                    str(ROOT / ".claude/hooks/py.sh"),
                    str(ROOT / ".claude/hooks" / script),
                ],
                cwd=nested,
                env=environment,
                input="{}\n",
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(
            [
                shell,
                str(ROOT / ".claude/hooks/py.sh"),
                str(ROOT / "scripts/harness/sync_agent_harness.py"),
                "--if-stale",
                "--quiet",
            ],
            cwd=nested,
            env=environment,
            input="{}\n",
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_sync_stale_and_orphan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / ".claude", root / ".claude")
            (root / ".codex/agents").mkdir(parents=True)
            shutil.copy2(
                ROOT / ".codex/AGENTS.header.md", root / ".codex/AGENTS.header.md"
            )
            shutil.copy2(ROOT / "CLAUDE.md", root / "CLAUDE.md")
            with (
                patch.object(sync, "ROOT", root),
                patch.object(sys, "argv", ["sync", "--quiet"]),
            ):
                self.assertEqual(sync.main(), 0)
                orphan = root / ".codex/agents/orphan.toml"
                orphan.write_text("x")
                with patch.object(sys, "argv", ["sync", "--check", "--quiet"]):
                    self.assertEqual(sync.main(), 1)
                self.assertEqual(sync.main(), 0)
                self.assertFalse(orphan.exists())
                with patch.object(sys, "argv", ["sync", "--check", "--quiet"]):
                    self.assertEqual(sync.main(), 0)


if __name__ == "__main__":
    unittest.main()

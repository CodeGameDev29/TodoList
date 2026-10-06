from __future__ import annotations
import importlib.util, json, os, shutil, subprocess, sys, tempfile, tomllib, unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("qa_harness", ROOT / "qa/harness.py")
qa = importlib.util.module_from_spec(spec); spec.loader.exec_module(qa)
validator_spec = importlib.util.spec_from_file_location("harness_validator", ROOT / "scripts/harness/validate_harness.py")
validator = importlib.util.module_from_spec(validator_spec); validator_spec.loader.exec_module(validator)

class HarnessApplicationTransitionTests(unittest.TestCase):
    def test_scan_excludes_dependencies_and_runtime_but_keeps_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            (root / ".gitignore").write_text("node_modules/\n.qa-artifacts/\n.playwright-mcp/\n")
            for directory in ("node_modules", ".qa-artifacts", ".playwright-mcp/traces", "apps/api"):
                (root / directory).mkdir(parents=True)
            for filename in ("node_modules/package.json", ".qa-artifacts/run.log", ".playwright-mcp/traces/runtime.trace", "apps/api/source.js", "package.json"):
                (root / filename).write_text("sample")
            files = {path.relative_to(root).as_posix() for path in validator.source_files(root)}
            self.assertEqual(files, {".gitignore", "apps/api/source.js", "package.json"})

    def test_populated_qa_state_is_valid_and_unknown_class_is_rejected(self):
        registry = {"schema_version": 1, "classes": [{"schema_version": 1, "id": "C1", "title": "Failure", "regression_rows": [{"id": "one"}]}]}
        entry = {"state": "open", "events": [], "regression_rows": {"one": "UNRUN"}, "clean_rounds": 0, "process_failure": False, "last_shipped_change": None}
        validator.check_qa_state(registry, {"schema_version": 2, "classes": {"C1": entry}})
        with self.assertRaises(SystemExit):
            validator.check_qa_state(registry, {"schema_version": 2, "classes": {"unknown": entry}})
        entry["regression_rows"]["one"] = "MAYBE"
        with self.assertRaises(SystemExit):
            validator.check_qa_state(registry, {"schema_version": 2, "classes": {"C1": entry}})

class CodexSemanticValidationTests(unittest.TestCase):
    def test_isolated_home_uses_user_cache_cleans_up_and_has_no_credentials(self):
        original_config = (ROOT / ".codex/config.toml").read_bytes()
        with tempfile.TemporaryDirectory() as user_home:
            with patch.object(validator.Path, "home", return_value=Path(user_home)), patch.dict(os.environ, {"OPENAI_API_KEY": "test-only", "CODEX_API_KEY": "test-only"}):
                with validator.isolated_codex_environment() as environment:
                    home = Path(environment["CODEX_HOME"])
                    self.assertEqual(home.parent, Path(user_home) / ".cache/todolist-harness-validation")
                    self.assertNotIn("OPENAI_API_KEY", environment)
                    self.assertNotIn("CODEX_API_KEY", environment)
                    self.assertFalse((home / "auth.json").exists())
                    self.assertEqual(tomllib.loads((home / "config.toml").read_text())["projects"][str(ROOT)]["trust_level"], "trusted")
                self.assertFalse(home.exists())
        self.assertEqual((ROOT / ".codex/config.toml").read_bytes(), original_config)

    def test_real_cli_accepts_valid_config_without_credentials_and_rejects_unknown_field(self):
        codex = shutil.which("codex")
        self.assertIsNotNone(codex, "Pinned Codex is required for semantic regression coverage")
        validator.semantic_codex()
        with validator.isolated_codex_environment() as environment:
            config = Path(environment["CODEX_HOME"]) / "config.toml"
            config.write_text("unsupported_field_for_regression = true\n" + config.read_text())
            with self.assertRaisesRegex(SystemExit, "unknown configuration field.*unsupported_field_for_regression"):
                validator.run_semantic_command([codex, "app-server", "--strict-config", "--stdio"], environment)

    def test_semantic_failure_preserves_both_diagnostic_streams(self):
        result = subprocess.CompletedProcess(["codex", "command"], 1, stdout="actual failure", stderr="helper warning")
        with patch.object(validator.subprocess, "run", return_value=result) as run:
            with self.assertRaises(SystemExit) as failure:
                validator.run_semantic_command(["codex", "command"], {})
        self.assertIn("stdout: actual failure", str(failure.exception))
        self.assertIn("stderr: helper warning", str(failure.exception))
        self.assertEqual(run.call_args.kwargs["input"], "")
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    def test_semantic_timeout_is_a_hard_failure(self):
        with patch.object(validator.subprocess, "run", side_effect=subprocess.TimeoutExpired(["codex"], 30)):
            with self.assertRaisesRegex(SystemExit, "timed out"):
                validator.run_semantic_command(["codex", "command"], {})

class QAHarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.old = qa.QA, qa.ART, qa.STATE
        qa.QA, qa.ART, qa.STATE = self.root / "qa", self.root / "artifacts", self.root / "state"
        (qa.QA / "journeys").mkdir(parents=True); qa.ART.mkdir(); qa.STATE.mkdir()
        qa.save(qa.STATE / "bug-classes.json", {"schema_version":1,"classes":[]}); qa.save(qa.STATE / "ledger.json", {"schema_version":2,"classes":{}})
        self.journey = {"schema_version":1,"id":"journey","title":"Example","kind":"ui-only","base_url_env":"TODO_URL","steps":[{"id":"one","expectation":"visible","tdd_expect":"PASS","actions":[{"type":"navigate","url":"/"}]}]}
        qa.save(qa.QA / "journeys/journey.json", self.journey)
        for name in ("shot.png","trace.zip","console.log","network.json"): (qa.ART / name).write_text("evidence")
    def tearDown(self): qa.QA, qa.ART, qa.STATE = self.old; self.tmp.cleanup()
    def report(self, result="FAIL", class_id="C1", change="change-a"):
        evidence = {key:str(qa.ART / name) for key,name in {"screenshot":"shot.png","trace":"trace.zip","console":"console.log","network":"network.json"}.items()}
        return {"schema_version":1,"id":"r-"+result+change,"journey_id":"journey","phase":"red" if result=="FAIL" else "green","complete":True,"run_valid":True,"runner":{"identity":"runner"},"started_at":"2026-01-01T00:00:00Z","finished_at":"2026-01-01T00:00:01Z","browser":{"headed":True,"foreground":True,"title":"TodoList"},"wall_clock_ms":1000,"steps":[{"id":"one","result":result,"evidence":evidence}],"judge":{"identity":"judge","verdict":result,"rows":[{"step_id":"one","verdict":result,"class_id":class_id}]},"change_id":change}
    def add_class(self): qa.save(qa.STATE / "bug-classes.json", {"schema_version":1,"classes":[{"schema_version":1,"id":"C1","title":"Class one","regression_rows":[{"id":"one"}]}]})
    def test_positive_journey_preflight(self): self.assertIsNone(qa.validate_journey(self.journey))
    def test_headless_and_network_bypass_refused(self):
        bad=json.loads(json.dumps(self.journey)); bad["steps"][0]["headless"]=True; self.assertIn("headless",qa.validate_journey(bad))
        bad=json.loads(json.dumps(self.journey)); bad["steps"][0]["actions"]=[{"type":"fetch","url":"/"}]; self.assertIn("allowed UI",qa.validate_journey(bad))
    def test_valid_report_and_missing_evidence(self):
        self.add_class(); report=self.report(); self.assertIsNone(qa.validate_report(report)); report["steps"][0]["evidence"]["screenshot"]=str(self.root/"outside.png"); self.assertIn("screenshot",qa.validate_report(report))
    def test_runner_judge_and_third_verdict_refusals(self):
        self.add_class(); report=self.report(); report["judge"]["identity"]="runner"; self.assertIn("independent",qa.validate_report(report)); report=self.report(); report["judge"]["verdict"]="MAYBE"; self.assertIn("verdict",qa.validate_report(report))
    def test_missing_extra_rows_and_unknown_class(self):
        self.add_class(); report=self.report(); report["judge"]["rows"]=[]; self.assertIn("cover every",qa.validate_report(report)); report=self.report(class_id="unknown"); self.assertIn("unknown class",qa.validate_report(report))
    def test_proposed_class_and_invalid_run_refusal(self):
        report=self.report(); report["judge"]["rows"][0].pop("class_id"); report["judge"]["rows"][0]["proposed_class_id"]="C1"; report["proposed_classes"]=[{"schema_version":1,"id":"C1","title":"Class one","regression_rows":[{"id":"one"}]}]; self.assertIsNone(qa.validate_report(report)); report["run_valid"]=False
        with self.assertRaises(ValueError): qa.record(report)
    def test_per_class_red_green_regression_and_closure(self):
        self.add_class(); qa.record(self.report("FAIL",change="same")); qa.record(self.report("FAIL",change="same")); entry=qa.load(qa.STATE/"ledger.json")["classes"]["C1"]; self.assertTrue(entry["process_failure"]); self.assertEqual(entry["state"],"open")
        qa.record(self.report("PASS",change="fix")); qa.record(self.report("PASS",change="fix2")); self.assertEqual(qa.load(qa.STATE/"ledger.json")["classes"]["C1"]["state"],"closed")
        qa.record(self.report("FAIL",change="regression")); self.assertEqual(qa.load(qa.STATE/"ledger.json")["classes"]["C1"]["state"],"open")

class HarnessConfigTests(unittest.TestCase):
    def test_sync_config_roles_hooks_and_pins(self):
        self.assertEqual(subprocess.run([sys.executable,"scripts/harness/sync_agent_harness.py","--check"],cwd=ROOT).returncode,0)
        self.assertEqual(subprocess.run([sys.executable,"scripts/harness/validate_harness.py"],cwd=ROOT).returncode,0)
        self.assertIn("@playwright/mcp@0.0.83",(ROOT/".mcp.json").read_text()); self.assertIn("model_reasoning_effort",(ROOT/".codex/agents/verifier.toml").read_text())
    def test_claude_settings_exact_shape(self):
        settings=json.loads((ROOT/".claude/settings.json").read_text())
        self.assertEqual(settings["modelSettings"], {"claude-fable-5-1":{"effortLevel":"high","maxEffortLevel":"xhigh"},"claude-opus-5-5":{"effortLevel":"medium","maxEffortLevel":"high"}})
        self.assertEqual(settings["env"], {"CLAUDE_CODE_SUBAGENT_MODEL":"claude-opus-5-5","CLAUDE_CODE_SUBAGENT_MODEL_FORCE":"1","CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS":"4","CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH":"2"})
        self.assertFalse({"orchestrator","agents","reasoningEffort","mcpServers","crossSessionInbound"} & settings.keys())
        for rows in settings["hooks"].values():
            for row in rows:
                for hook in row["hooks"]:
                    self.assertNotIn("commandWindows",hook); self.assertTrue(hook["command"].startswith('sh "$CLAUDE_PROJECT_DIR/.claude/hooks/py.sh"'))
    def test_claude_hooks_run_from_nested_directory(self):
        shell=shutil.which("sh")
        if not shell: self.skipTest("POSIX sh (Git Bash) is unavailable on this Windows host")
        environment=os.environ.copy(); environment["CLAUDE_PROJECT_DIR"]=str(ROOT)
        nested=ROOT/"apps/web"
        for script in ("session_start.py","project_rules_reminder.py","output_meter.py","completion_referee.py"):
            result=subprocess.run([shell,str(ROOT/".claude/hooks/py.sh"),str(ROOT/".claude/hooks"/script)],cwd=nested,env=environment,input='{}\n',text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
        result=subprocess.run([shell,str(ROOT/".claude/hooks/py.sh"),str(ROOT/"scripts/harness/sync_agent_harness.py"),"--if-stale","--quiet"],cwd=nested,env=environment,input='{}\n',text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_sync_stale_and_orphan(self):
        orphan=ROOT/".codex/agents/orphan.toml"; orphan.write_text("x"); self.assertNotEqual(subprocess.run([sys.executable,"scripts/harness/sync_agent_harness.py","--check"],cwd=ROOT).returncode,0); self.assertEqual(subprocess.run([sys.executable,"scripts/harness/sync_agent_harness.py"],cwd=ROOT).returncode,0); self.assertFalse(orphan.exists())
if __name__ == "__main__": unittest.main()

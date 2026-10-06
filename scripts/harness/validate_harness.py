#!/usr/bin/env python3
"""Validate TodoList harness sources, mirrors, contracts, and Codex semantic load."""
from __future__ import annotations
import json, os, runpy, shutil, subprocess, sys, tempfile, tomllib
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLES = {"executor", "executor-hard", "verifier", "qa-runner", "qa-judge", "security-reviewer"}
READ_ONLY = {"verifier", "qa-judge", "security-reviewer"}; MCP = "@playwright/mcp@0.0.83"
def fail(message): raise SystemExit(f"FAIL: {message}")
def source_files(root=ROOT):
    """Scan tracked and nonignored source, without walking dependencies or runtime artifacts."""
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root, capture_output=True)
    if result.returncode: fail("Git source enumeration failed")
    return [root / os.fsdecode(name) for name in result.stdout.split(b"\0") if name and (root / os.fsdecode(name)).is_file()]

def check_qa_state(registry, ledger):
    valid_class = runpy.run_path(str(ROOT / "qa/harness.py"))["valid_class"]
    if not isinstance(registry, dict) or registry.get("schema_version") != 1 or not isinstance(registry.get("classes"), list): fail("QA registry schema")
    definitions = registry["classes"]
    if not all(valid_class(item) for item in definitions): fail("QA class definition")
    ids = [item["id"] for item in definitions]
    if len(ids) != len(set(ids)): fail("duplicate QA class")
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 2 or not isinstance(ledger.get("classes"), dict): fail("QA ledger schema")
    for class_id, entry in ledger["classes"].items():
        if class_id not in ids or not isinstance(entry, dict): fail("unknown QA ledger class")
        if entry.get("state") not in {"open", "closed"} or not isinstance(entry.get("events"), list) or not isinstance(entry.get("regression_rows"), dict) or not isinstance(entry.get("clean_rounds"), int) or not isinstance(entry.get("process_failure"), bool) or "last_shipped_change" not in entry: fail("QA ledger entry")
        expected_rows = {row["id"] for item in definitions if item["id"] == class_id for row in item["regression_rows"]}
        if set(entry["regression_rows"]) != expected_rows or any(value not in {"UNRUN", "PASS", "FAIL"} for value in entry["regression_rows"].values()): fail("QA regression rows")
def frontmatter(path):
    text = path.read_text().replace("\r\n", "\n")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]: fail(f"agent frontmatter {path.name}")
    header = text[4:text.find("\n---\n", 4)]
    return {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip().strip('"') for line in header.splitlines() if ":" in line}
def check_hooks(hooks, label, require_matcher):
    if not isinstance(hooks, dict): fail(f"{label} hooks")
    for event, rows in hooks.items():
        if not isinstance(rows, list) or not rows: fail(f"{label} {event}")
        for row in rows:
            if (require_matcher and "matcher" not in row) or not isinstance(row.get("hooks"), list): fail(f"{label} hook row")
            for hook in row["hooks"]:
                if hook.get("type") != "command" or not hook.get("command") or not isinstance(hook.get("timeout"), int): fail(f"{label} nested hook")
@contextmanager
def isolated_codex_environment():
    # Codex refuses helper aliases under /tmp. Keep an isolated, disposable home
    # under the user's cache, never their real Codex configuration or credentials.
    parent = Path.home() / ".cache" / "todolist-harness-validation"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="todolist-codex-", dir=parent) as home:
        config = Path(home) / "config.toml"
        shutil.copy2(ROOT / ".codex/config.toml", config)
        shutil.copytree(ROOT / ".codex/agents", Path(home) / "agents")
        # The app server otherwise disables project-local configuration in a new
        # home. Trust only this already-validated checkout in the disposable copy.
        with config.open("a", encoding="utf-8") as target:
            target.write('\n[projects.' + json.dumps(str(ROOT)) + ']\ntrust_level = "trusted"\n')
        env = os.environ.copy(); env["CODEX_HOME"] = home
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY"):
            env.pop(key, None)
        yield env

def run_semantic_command(command, env):
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, input="", text=True, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        fail("Codex semantic project load timed out: " + " ".join(command[1:]))
    if result.returncode:
        fail("Codex semantic project load failed (" + " ".join(command[1:]) + ")"
             + "\nstdout: " + result.stdout[-2000:] + "\nstderr: " + result.stderr[-2000:])

def semantic_codex():
    codex = shutil.which("codex")
    if not codex: fail("Codex 0.160.1 must be installed for semantic validation")
    if "0.160.1" not in subprocess.run([codex, "--version"], text=True, capture_output=True).stdout: fail("Codex must be pinned to 0.160.1")
    with isolated_codex_environment() as env:
        # Startup strictly loads config and agent definitions, then EOF shuts the
        # stdio server down without any requests or model calls. Doctor also tests
        # login/network health and cannot succeed in credential-free public CI.
        run_semantic_command([codex, "app-server", "--strict-config", "--stdio"], env)
        run_semantic_command([codex, "debug", "prompt-input", "x"], env)
def main():
    if subprocess.run([sys.executable, "scripts/harness/sync_agent_harness.py", "--check"], cwd=ROOT).returncode: fail("generated mirror stale")
    config = tomllib.loads((ROOT / ".codex/config.toml").read_text())
    required = {"model":"gpt-6-astra", "model_reasoning_effort":"high", "project_doc_max_bytes":262144, "tool_output_token_limit":4000, "web_search":"live", "approval_policy":"on-request", "sandbox_mode":"workspace-write"}
    for key, value in required.items():
        if config.get(key) != value: fail(f"Codex config {key}")
    if config.get("project_doc_fallback_filenames") != ["CLAUDE.md"] or config.get("sandbox_workspace_write", {}).get("network_access") is not True or config.get("shell_environment_policy", {}).get("inherit") != "all": fail("Codex workspace policy")
    if config.get("features") != {"hooks": True, "multi_agent": True}: fail("Codex feature policy")
    if config.get("agents", {}).get("default_subagent_model") != "gpt-6.1-sol" or config["agents"].get("max_concurrent_threads_per_session") != 4: fail("Codex subagent policy")
    mcp = json.loads((ROOT / ".mcp.json").read_text()); cmcp = config.get("mcp_servers", {}).get("playwright", {})
    if MCP not in json.dumps(mcp) or cmcp.get("command") != "npx" or cmcp.get("args") != ["-y", MCP]: fail("Playwright MCP pin")
    settings = json.loads((ROOT / ".claude/settings.json").read_text())
    wrong = {"orchestrator", "agents", "reasoningEffort", "mcpServers", "crossSessionInbound"}
    model_settings = settings.get("modelSettings")
    expected_models = {"claude-fable-5-1": {"effortLevel":"high", "maxEffortLevel":"xhigh"}, "claude-opus-5-5": {"effortLevel":"medium", "maxEffortLevel":"high"}}
    expected_env = {"CLAUDE_CODE_SUBAGENT_MODEL":"claude-opus-5-5", "CLAUDE_CODE_SUBAGENT_MODEL_FORCE":"1", "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS":"4", "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH":"2"}
    if wrong & settings.keys() or settings.get("model") != "claude-fable-5-1" or settings.get("effortLevel") != "high" or model_settings != expected_models or settings.get("ultracode") is not False or settings.get("workflowKeywordTriggerEnabled") is not False or settings.get("bashOutputMaxChars") != 8000 or settings.get("env") != expected_env: fail("Claude settings policy")
    check_hooks(settings.get("hooks"), "Claude", False)
    for rows in settings["hooks"].values():
        for row in rows:
            for hook in row["hooks"]:
                command = hook["command"]
                if "commandWindows" in hook or not command.startswith('sh "$CLAUDE_PROJECT_DIR/.claude/hooks/py.sh" "$CLAUDE_PROJECT_DIR/'):
                    fail("Claude hook command shape")
    if [row.get("matcher") for row in settings["hooks"]["PostToolUse"]] != ["Bash", "Edit|Write|MultiEdit"] or settings["hooks"]["PostToolUseFailure"][0].get("matcher") != "Bash": fail("Claude hook matchers")
    status = settings.get("statusLine", {})
    if status.get("type") != "command" or not status.get("command", "").startswith('sh "$CLAUDE_PROJECT_DIR/.claude/hooks/py.sh"') or status.get("padding") != 0 or status.get("refreshInterval") != 60: fail("Claude status line")
    hooks = json.loads((ROOT / ".codex/hooks.json").read_text())
    if not hooks.get("description") or "PostToolUseFailure" in hooks.get("hooks", {}): fail("Codex hook schema")
    check_hooks(hooks.get("hooks"), "Codex", True)
    for role in ROLES:
        meta = frontmatter(ROOT / ".claude/agents" / f"{role}.md")
        if meta.get("name") != role or meta.get("model") != "claude-opus-5-5" or meta.get("effort") not in {"medium", "high"}: fail(f"canonical role {role}")
        generated = tomllib.loads((ROOT / ".codex/agents" / f"{role}.toml").read_text())
        if generated.get("name") != role or generated.get("model") != "gpt-6.1-sol" or "developer_instructions" not in generated or "reasoning_effort" in generated or "instructions_file" in generated: fail(f"generated role {role}")
        if role in READ_ONLY and generated.get("sandbox_mode") != "read-only": fail(f"read-only role {role}")
    for meta in (ROOT / ".claude/skills").glob("*/agents/openai.yaml"):
        text = meta.read_text(); name = meta.parents[1].name
        if 'display_name: "' not in text or "Help with" in text or f"${name}" not in text: fail(f"skill metadata {name}")
    check_qa_state(json.loads((ROOT / "qa/bug-classes.json").read_text()), json.loads((ROOT / "qa/ledger.json").read_text()))
    ignored = (ROOT / ".gitignore").read_text()
    if ".qa-artifacts/" not in ignored or ".codex/tmp/" not in ignored: fail("runtime ignores")
    manifest = json.loads((ROOT / "package.json").read_text())
    if manifest.get("private") is not True or manifest.get("workspaces") != ["apps/api", "apps/web"] or manifest.get("engines", {}).get("node") != ">=24.15.0 <25": fail("approved application workspace contract")
    files = source_files()
    if any(path.suffix == ".bat" and ".codex" in path.relative_to(ROOT).parts for path in files): fail("Codex batch runtime residue")
    appdata = "App" + "Data"
    for path in files:
        if appdata in path.read_text(encoding="utf-8", errors="ignore"):
            fail("absolute local runtime path in " + str(path.relative_to(ROOT)))
    semantic_codex(); print("harness validation passed")
if __name__ == "__main__": main()

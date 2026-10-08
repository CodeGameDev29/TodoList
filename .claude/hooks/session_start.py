import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
state = (ROOT / "PROJECT-STATE.md").read_text(encoding="utf-8").splitlines()[2]
mirrors_current = (
    subprocess.run(
        [sys.executable, "scripts/harness/sync_agent_harness.py", "--check", "--quiet"],
        cwd=ROOT,
    ).returncode
    == 0
)
print(f"{state} | mirrors: {'current' if mirrors_current else 'STALE'}")

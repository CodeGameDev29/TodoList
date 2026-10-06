#!/usr/bin/env python3
from __future__ import annotations
import shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
subprocess.check_call([sys.executable,"scripts/harness/sync_agent_harness.py"],cwd=ROOT)
subprocess.check_call(["git","config","core.hooksPath",".githooks"],cwd=ROOT)
for x in ("codex","claude","node","npm"):
    print(f"{x}: {shutil.which(x) or 'not found'}")
print("Manual Codex steps: run `codex`, use `/hooks` to trust project hooks, then `codex login` if needed. This setup does not change login/account state.")

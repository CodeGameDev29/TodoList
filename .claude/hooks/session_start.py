from pathlib import Path
import subprocess, sys
r=Path(__file__).resolve().parents[2]; state=(r/'PROJECT-STATE.md').read_text().splitlines()[2]; ok=subprocess.run([sys.executable,'scripts/harness/sync_agent_harness.py','--check','--quiet'],cwd=r).returncode==0
print(f'{state} | mirrors: {"current" if ok else "STALE"}')

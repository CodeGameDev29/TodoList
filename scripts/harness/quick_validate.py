#!/usr/bin/env python3
"""Quick stdlib validation for canonical and generated TodoList skills."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def fail(message):
    raise SystemExit("FAIL: " + message)


for source_root, generated_root in (
    (ROOT / ".claude/skills", ROOT / ".agents/skills"),
):
    for skill in sorted(source_root.glob("*/SKILL.md")):
        name = skill.parent.name
        generated = generated_root / skill.relative_to(source_root)
        if (
            not generated.exists()
            or name not in skill.read_text()
            or name not in generated.read_text()
        ):
            fail(f"skill mirror {name}")
        for root in (source_root, generated_root):
            meta = (root / name / "agents/openai.yaml").read_text()
            lines = {
                line.strip().split(":", 1)[0]: line.strip()
                .split(":", 1)[1]
                .strip()
                .strip('"')
                for line in meta.splitlines()
                if ":" in line
            }
            description = lines.get("short_description", "")
            if (
                not lines.get("display_name")
                or not 25 <= len(description) <= 64
                or f"${name}" not in lines.get("default_prompt", "")
            ):
                fail(f"skill metadata {root.name}/{name}")
print("skill validation passed")

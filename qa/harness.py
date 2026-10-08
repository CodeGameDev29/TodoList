#!/usr/bin/env python3
"""Stdlib-only evidence contracts and per-class QA ledger for TodoList."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "qa"
ART = Path(os.environ.get("TODOLIST_QA_ARTIFACTS", ROOT / ".qa-artifacts")).resolve()
STATE = Path(os.environ.get("TODOLIST_QA_STATE_ROOT", QA)).resolve()
UI_ACTIONS = {
    "navigate",
    "click",
    "fill",
    "select",
    "press",
    "check",
    "uncheck",
    "upload",
    "screenshot",
    "wait_for",
    "assert_text",
    "assert_visible",
}
BYPASS_WORDS = {
    "fetch",
    "xhr",
    "websocket",
    "evaluate",
    "api_request",
    "request",
    "http_request",
}
RESERVED_REPORT_IDS = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}" for prefix in ("COM", "LPT") for number in range(1, 10)
}


def valid_report_id(value):
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) is not None
        and value.upper() not in RESERVED_REPORT_IDS
    )


def artifact_directory(folder):
    root = ART.resolve()
    directory = (root / folder).resolve()
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{folder} directory resolves outside artifact root") from exc
    return directory


def artifact_json_path(folder, report_id):
    if not valid_report_id(report_id):
        raise ValueError("report ID must be a safe ASCII filename identifier")
    directory = artifact_directory(folder)
    path = (directory / f"{report_id}.json").resolve()
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise ValueError(f"report path resolves outside {folder} directory") from exc
    return path


def validate_timing(data, where):
    timestamps = []
    for field in ("started_at", "finished_at"):
        value = data[field]
        if not isinstance(value, str):
            return f"{where}: {field} must be a timezone-aware timestamp"
        try:
            timestamp = datetime.fromisoformat(value)
        except ValueError:
            return f"{where}: {field} must be a valid timezone-aware timestamp"
        if timestamp.utcoffset() is None:
            return f"{where}: {field} must include a timezone"
        timestamps.append(timestamp)
    if timestamps[1] < timestamps[0]:
        return f"{where}: finished_at must not precede started_at"
    duration = data["wall_clock_ms"]
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration < 0
        or (isinstance(duration, float) and not math.isfinite(duration))
    ):
        return f"{where}: wall_clock_ms must be a nonnegative finite number"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def inside_artifact(value):
    try:
        path = Path(value).resolve()
        path.relative_to(ART)
        return path.is_file()
    except (ValueError, OSError):
        return False


def journey_files():
    return sorted(
        path
        for folder in (QA / "acceptance", QA / "journeys")
        if folder.exists()
        for path in folder.rglob("*.json")
    )


def validate_action(action, where):
    if not isinstance(action, dict) or set(action) - {
        "type",
        "selector",
        "text",
        "value",
        "url",
        "timeout_ms",
        "path",
        "expectation",
    }:
        return f"{where}: unsupported action shape"
    if action.get("type") not in UI_ACTIONS:
        return f"{where}: action {action.get('type')!r} is not an allowed UI action"
    if any(word in json.dumps(action).lower() for word in BYPASS_WORDS):
        return f"{where}: direct browser/network bypass action"
    if action["type"] == "navigate":
        url = action.get("url")
        if not isinstance(url, str) or not (
            url.startswith("/") or url.startswith("${") or "://" not in url
        ):
            return f"{where}: navigate URL must be relative or use base_url_env"


def validate_journey(data, where="journey"):
    required = {"schema_version", "id", "title", "kind", "base_url_env", "steps"}
    if not isinstance(data, dict) or required - data.keys():
        return f"{where}: missing journey contract fields"
    if (
        data["schema_version"] != 1
        or data["kind"] != "ui-only"
        or not isinstance(data["base_url_env"], str)
    ):
        return f"{where}: invalid journey identity"
    if not isinstance(data["steps"], list) or not data["steps"]:
        return f"{where}: steps must be a non-empty list"
    ids = set()
    for step in data["steps"]:
        if (
            not isinstance(step, dict)
            or {"id", "expectation", "tdd_expect", "actions"} - step.keys()
        ):
            return f"{where}: invalid step"
        if step["id"] in ids or step["tdd_expect"] not in {"PASS", "FAIL"}:
            return f"{where}: duplicate step id or invalid tdd_expect"
        ids.add(step["id"])
        if not isinstance(step["actions"], list) or not step["actions"]:
            return f"{where}: step actions required"
        raw = json.dumps(step).lower()
        if '"headless": true' in raw or '"headless":true' in raw:
            return f"{where}: headless journeys are forbidden"
        for action in step["actions"]:
            error = validate_action(action, f"{where}/{step['id']}")
            if error:
                return error


def get_journey(journey_id):
    for path in journey_files():
        data = load(path)
        if data.get("id") == journey_id:
            return data


def validate_evidence(evidence, where):
    if not isinstance(evidence, dict) or not evidence:
        return f"{where}: evidence required"
    if not isinstance(evidence.get("screenshot"), str) or not inside_artifact(
        evidence["screenshot"]
    ):
        return f"{where}: screenshot is missing or outside artifact root"
    for key in ("trace", "console", "network"):
        value = evidence.get(key)
        if value != "captured-empty" and (
            not isinstance(value, str) or not inside_artifact(value)
        ):
            return f"{where}: {key} must be evidence path or captured-empty"


def valid_class(item):
    return (
        isinstance(item, dict)
        and item.get("schema_version") == 1
        and isinstance(item.get("id"), str)
        and bool(item.get("title"))
        and isinstance(item.get("regression_rows"), list)
        and all(
            isinstance(row, dict) and row.get("id") for row in item["regression_rows"]
        )
    )


def validate_report(data, where="report"):
    required = {
        "schema_version",
        "id",
        "journey_id",
        "phase",
        "complete",
        "run_valid",
        "runner",
        "started_at",
        "finished_at",
        "browser",
        "wall_clock_ms",
        "steps",
        "judge",
        "change_id",
    }
    if not isinstance(data, dict) or required - data.keys():
        return f"{where}: missing runtime report fields"
    if not valid_report_id(data["id"]):
        return f"{where}: report ID must be a safe ASCII filename identifier"
    error = validate_timing(data, where)
    if error:
        return error
    if (
        data["schema_version"] != 1
        or data["phase"] not in {"red", "green", "regression"}
        or data["complete"] is not True
        or data["run_valid"] is not True
    ):
        return f"{where}: invalid run state"
    if not isinstance(data["runner"], dict) or not data["runner"].get("identity"):
        return f"{where}: runner identity required"
    browser = data["browser"]
    if (
        not isinstance(browser, dict)
        or browser.get("headed") is not True
        or browser.get("foreground") is not True
        or not browser.get("title")
    ):
        return f"{where}: headed foreground browser title required"
    journey = get_journey(data["journey_id"])
    if not journey:
        return f"{where}: unknown journey"
    error = validate_journey(journey, data["journey_id"])
    if error:
        return error
    ids = [step["id"] for step in journey["steps"]]
    if (
        not isinstance(data["steps"], list)
        or [step.get("id") for step in data["steps"]] != ids
    ):
        return f"{where}: report must cover every journey step exactly once in order"
    for step in data["steps"]:
        if step.get("result") not in {"PASS", "FAIL"}:
            return f"{where}: invalid step result"
        error = validate_evidence(step.get("evidence"), f"{where}/{step.get('id')}")
        if error:
            return error
    judge = data["judge"]
    if (
        not isinstance(judge, dict)
        or not judge.get("identity")
        or judge["identity"] == data["runner"]["identity"]
    ):
        return f"{where}: independent judge identity required"
    if judge.get("verdict") not in {"PASS", "FAIL"}:
        return f"{where}: judge verdict must be PASS or FAIL"
    rows = judge.get("rows")
    if not isinstance(rows, list) or [row.get("step_id") for row in rows] != ids:
        return (
            f"{where}: judge rows must cover every journey step exactly once in order"
        )
    results = {step["id"]: step["result"] for step in data["steps"]}
    for row in rows:
        if (
            row.get("verdict") not in {"PASS", "FAIL"}
            or row["verdict"] != results[row["step_id"]]
        ):
            return f"{where}: judge row is inconsistent with captured step result"
        if (
            row["verdict"] == "FAIL"
            and not row.get("class_id")
            and not row.get("proposed_class_id")
        ):
            return f"{where}: failing row must map to a class"
    if judge["verdict"] != (
        "PASS" if all(value == "PASS" for value in results.values()) else "FAIL"
    ):
        return f"{where}: overall judge verdict is inconsistent"
    known = {item["id"] for item in load(STATE / "bug-classes.json")["classes"]}
    proposals = {
        item.get("id"): item
        for item in data.get("proposed_classes", [])
        if isinstance(item, dict)
    }
    for row in rows:
        class_id = row.get("class_id") or row.get("proposed_class_id")
        if (
            class_id
            and class_id not in known
            and not valid_class(proposals.get(class_id))
        ):
            return f"{where}: unknown class without valid proposed class"


def intake_report(data):
    path = STATE / "bug-classes.json"
    registry = load(path)
    known = {item["id"] for item in registry["classes"]}
    for item in data.get("proposed_classes", []):
        if valid_class(item) and item["id"] not in known:
            registry["classes"].append(item)
            known.add(item["id"])
    save(path, registry)


def record(data):
    error = validate_report(data)
    if error:
        raise ValueError(error)
    path = STATE / "ledger.json"
    ledger = load(path)
    recorded_ids = set(ledger.get("recorded_report_ids", []))
    recorded_ids.update(
        event["report_id"]
        for entry in ledger["classes"].values()
        for event in entry["events"]
    )
    if data["id"] in recorded_ids:
        raise ValueError(f"report {data['id']!r} is already recorded")
    intake_report(data)
    defs = {item["id"]: item for item in load(STATE / "bug-classes.json")["classes"]}
    entries = ledger.setdefault("classes", {})
    assessed = {}
    for row in data["judge"]["rows"]:
        class_id = row.get("class_id") or row.get("proposed_class_id")
        if class_id:
            assessed.setdefault(class_id, []).append(row)
    for class_id, rows in assessed.items():
        definition = defs[class_id]
        entry = entries.setdefault(
            class_id,
            {
                "regression_rows": {
                    row["id"]: "UNRUN" for row in definition["regression_rows"]
                },
                "events": [],
                "clean_rounds": 0,
                "state": "open",
                "process_failure": False,
                "last_shipped_change": None,
            },
        )
        result = "FAIL" if any(row["verdict"] == "FAIL" for row in rows) else "PASS"
        previous = entry["events"][-1] if entry["events"] else None
        for row in rows:
            if row["step_id"] in entry["regression_rows"]:
                entry["regression_rows"][row["step_id"]] = row["verdict"]
        if result == "FAIL":
            if (
                previous
                and previous["result"] == "FAIL"
                and previous.get("change_id") == data.get("change_id")
            ):
                entry["process_failure"] = True
            entry["clean_rounds"] = 0
            entry["state"] = "open"
        else:
            if all(value == "PASS" for value in entry["regression_rows"].values()):
                entry["clean_rounds"] += 1
                if entry["clean_rounds"] >= 2:
                    entry["state"] = "closed"
        entry["last_shipped_change"] = (
            data.get("change_id") or entry["last_shipped_change"]
        )
        entry["events"].append(
            {
                "report_id": data["id"],
                "phase": data["phase"],
                "result": result,
                "change_id": data.get("change_id"),
                "at": data["finished_at"],
            }
        )
    ledger.setdefault("recorded_report_ids", []).append(data["id"])
    save(path, ledger)


def report_path(report_id):
    return artifact_json_path("reports", report_id)


def cmd_preflight():
    files = journey_files()
    for path in files:
        error = validate_journey(load(path), str(path.relative_to(ROOT)))
        if error:
            raise SystemExit(error)
    print(f"journey preflight passed ({len(files)} definitions)")


def cmd_new(args):
    path = report_path(args.id)
    if path.exists():
        raise SystemExit("report exists")
    save(
        path,
        {
            "schema_version": 1,
            "id": args.id,
            "journey_id": "",
            "phase": "red",
            "complete": False,
            "run_valid": False,
            "runner": {},
            "started_at": "",
            "finished_at": "",
            "browser": {},
            "wall_clock_ms": 0,
            "steps": [],
            "judge": {},
            "change_id": None,
        },
    )
    print(path)


def cmd_validate(args):
    cmd_preflight()
    directory = artifact_directory("reports")
    for candidate in sorted(directory.glob("*.json")) if directory.exists() else []:
        path = report_path(candidate.stem)
        error = validate_report(load(path), str(path))
        if error:
            raise SystemExit(error)
    print("qa validation passed")


def cmd_pack(args):
    path = report_path(args.id)
    if not path.exists():
        raise SystemExit("report not found")
    data = load(path)
    error = validate_report(data, str(path))
    if error:
        raise SystemExit(f"cannot prepare judge pack: {error}")
    out = artifact_json_path("judge-packs", args.id)
    save(out, copy.deepcopy(data))
    print(out)


def cmd_add_class(args):
    item = load(args.class_file)
    if not valid_class(item):
        raise SystemExit("invalid class definition")
    path = STATE / "bug-classes.json"
    registry = load(path)
    if any(old["id"] == item["id"] for old in registry["classes"]):
        raise SystemExit("class already exists")
    registry["classes"].append(item)
    save(path, registry)
    print(item["id"])


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new-report")
    new.add_argument("id")
    sub.add_parser("preflight")
    sub.add_parser("validate")
    pack = sub.add_parser("judge-pack")
    pack.add_argument("id")
    add = sub.add_parser("add-class")
    add.add_argument("class_file")
    intake = sub.add_parser("intake")
    intake.add_argument("id")
    rec = sub.add_parser("record")
    rec.add_argument("id")
    sub.add_parser("status")
    args = parser.parse_args()
    try:
        dispatch(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def dispatch(args):
    if args.command == "new-report":
        cmd_new(args)
    elif args.command == "preflight":
        cmd_preflight()
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "judge-pack":
        cmd_pack(args)
    elif args.command == "add-class":
        cmd_add_class(args)
    elif args.command == "intake":
        data = load(report_path(args.id))
        error = validate_report(data)
        if error:
            raise SystemExit(error)
        intake_report(data)
        print("intake complete")
    elif args.command == "record":
        record(load(report_path(args.id)))
        print("recorded")
    else:
        print(json.dumps(load(STATE / "ledger.json"), indent=2))


if __name__ == "__main__":
    main()

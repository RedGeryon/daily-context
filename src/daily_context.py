#!/usr/bin/env python3
"""Dependency-free storage and indexing for Daily Context."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Iterable


VERSION = "0.1.0"
CONFIG_NAME = "context.config.json"
POINTER_NAME = ".daily-context.json"
KINDS = {"fact", "task", "decision", "goal", "risk", "assumption", "activity", "artifact"}
STATUSES = {
    "reported", "verified", "inferred", "proposed", "accepted", "open",
    "in_progress", "blocked", "waiting", "done", "contested", "superseded",
    "cancelled", "captured",
}
PREFIX = {
    "fact": "FACT", "task": "TASK", "decision": "DEC", "goal": "GOAL",
    "risk": "RISK", "assumption": "ASM", "activity": "ACT", "artifact": "ART",
}
PROFILE_HINTS = {
    "general": ["outcomes", "conversations", "decisions", "next actions", "work products"],
    "engineering": ["changes", "tests", "incidents", "decisions", "rollout and rollback", "repositories"],
    "research": ["questions", "sources", "observations", "inferences", "confidence", "open hypotheses"],
    "operations": ["events", "owners", "handoffs", "blockers", "service changes", "follow-up dates"],
}


class ContextError(RuntimeError):
    pass


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_day() -> str:
    return dt.datetime.now().astimezone().date().isoformat()


def day_path(root: Path, day: str) -> Path:
    year, month, _ = day.split("-")
    return root / "days" / year / month / day


def week_name(day: str | None = None) -> str:
    value = dt.date.fromisoformat(day or local_day())
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def json_read(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ContextError(f"Cannot read JSON from {path}: {exc}") from exc


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def json_write(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


@contextlib.contextmanager
def workspace_lock(root: Path, timeout: float = 5.0):
    lock = root / ".daily-context.lock"
    deadline = time.time() + timeout
    fd = None
    while fd is None:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, f"{os.getpid()}\n".encode())
        except FileExistsError:
            if time.time() >= deadline:
                raise ContextError(f"Daily Context is busy: {lock}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()


def find_root(start: str | Path | None = None, explicit: str | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    env_root = os.environ.get("DAILY_CONTEXT_DIR")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    current = Path(start or os.getcwd()).expanduser().resolve()
    for parent in (current, *current.parents):
        pointer = parent / POINTER_NAME
        if pointer.exists():
            data = json_read(pointer, {})
            configured = Path(str(data.get("path", ""))).expanduser()
            if not configured.is_absolute():
                configured = (parent / configured).resolve()
            candidates.append(configured)
        candidates.extend([parent, parent / "daily_context", parent / "daily-context"])
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / CONFIG_NAME).is_file():
            return resolved
    raise ContextError(
        "No Daily Context found. Pass --context, set DAILY_CONTEXT_DIR, "
        "or run `daily-context init ./daily_context`."
    )


def load_config(root: Path) -> dict[str, Any]:
    data = json_read(root / CONFIG_NAME)
    if not isinstance(data, dict):
        raise ContextError(f"Invalid configuration: {root / CONFIG_NAME}")
    return data


def ensure_day(root: Path, day: str) -> Path:
    base = day_path(root, day)
    for folder in (base / "raw", base / "derived", base / "work"):
        folder.mkdir(parents=True, exist_ok=True)
    ledger = base / "records.ndjson"
    if not ledger.exists():
        atomic_write(ledger, "")
    manifest = base / "manifest.json"
    if not manifest.exists():
        json_write(manifest, {"schema_version": 1, "date": day, "entities": []})
    summary = base / "derived" / "summary.md"
    if not summary.exists():
        atomic_write(summary, day_summary_template(day))
    return base


def read_records(root: Path, days: Iterable[str] | None = None) -> list[dict[str, Any]]:
    allowed = set(days or [])
    records: list[dict[str, Any]] = []
    for ledger in sorted((root / "days").glob("*/*/*/records.ndjson")):
        if allowed and ledger.parent.name not in allowed:
            continue
        for number, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContextError(f"Malformed record at {ledger}:{number}: {exc}") from exc
            item["_ledger"] = str(ledger.relative_to(root))
            records.append(item)
    return records


def next_id(records: list[dict[str, Any]], kind: str, day: str) -> str:
    prefix = PREFIX[kind]
    stem = f"{prefix}-{day}-"
    used = []
    for record in records:
        identifier = str(record.get("id", ""))
        if identifier.startswith(stem):
            with contextlib.suppress(ValueError):
                used.append(int(identifier.rsplit("-", 1)[1]))
    return f"{stem}{max(used, default=0) + 1:03d}"


def append_record(root: Path, record: dict[str, Any]) -> None:
    base = ensure_day(root, record["date"])
    ledger = base / "records.ndjson"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def add_record(
    root: Path,
    kind: str,
    text: str,
    status: str,
    sources: list[str] | None = None,
    owner: str | None = None,
    day: str | None = None,
    related: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in KINDS:
        raise ContextError(f"Unknown record kind: {kind}")
    if status not in STATUSES:
        raise ContextError(f"Unknown record status: {status}")
    chosen_day = day or local_day()
    existing = read_records(root)
    record = {
        "schema_version": 1,
        "id": next_id(existing, kind, chosen_day),
        "kind": kind,
        "status": status,
        "text": text.strip(),
        "date": chosen_day,
        "created_at": now_utc(),
        "created_by": owner or "unknown",
        "source_ids": sources or [],
        "related_ids": related or [],
    }
    if metadata:
        record["metadata"] = metadata
    append_record(root, record)
    if kind == "decision":
        write_decision(root, record)
    return record


def write_decision(root: Path, record: dict[str, Any]) -> None:
    target = root / "decisions" / f"{record['id']}.md"
    if target.exists():
        return
    sources = ", ".join(f"`{item}`" for item in record.get("source_ids", [])) or "None recorded"
    body = f"""# {record['id']} — {record['text']}

- **Status:** {record['status']}
- **Date:** {record['date']}
- **Owner:** {record['created_by']}
- **Evidence:** {sources}

## Context

Explain the circumstances and constraints that made this decision necessary.

## Decision

{record['text']}

## Alternatives considered

- Add alternatives when they materially explain the choice.

## Consequences

- Record positive, negative, and neutral consequences.

## Supersession

Not superseded.
"""
    atomic_write(target, body)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    clean = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in clean.split("-") if part)[:64] or "source"


def register_source(
    root: Path,
    source: Path | None,
    title: str,
    source_kind: str,
    sensitivity: str,
    copy_source: bool,
    day: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chosen_day = day or local_day()
    records = read_records(root)
    identifier = f"SRC-{chosen_day}-{sum(1 for r in records if str(r.get('id', '')).startswith(f'SRC-{chosen_day}-')) + 1:03d}"
    base = ensure_day(root, chosen_day)
    stored_path = None
    origin = None
    digest = None
    media_type = "application/octet-stream"
    if source:
        source = source.expanduser().resolve()
        if not source.is_file():
            raise ContextError(f"Source file does not exist: {source}")
        origin = f"file:{source.name}"
        suffix = source.suffix.lower()
        media_type = {
            ".md": "text/markdown", ".txt": "text/plain", ".json": "application/json",
            ".jsonl": "application/x-ndjson", ".ndjson": "application/x-ndjson",
            ".pdf": "application/pdf", ".csv": "text/csv",
        }.get(suffix, media_type)
        digest = sha256(source)
        if copy_source:
            destination = base / "raw" / f"{identifier.lower()}-{slug(title)}{suffix}"
            shutil.copy2(source, destination)
            stored_path = str(destination.relative_to(root))
        local_locations_path = root / ".source-locations.local.json"
        local_locations = json_read(local_locations_path, {})
        local_locations[identifier] = str(source)
        json_write(local_locations_path, local_locations)
    entity = {
        "id": identifier,
        "type": "source",
        "title": title,
        "source_kind": source_kind,
        "sensitivity": sensitivity,
        "captured_at": now_utc(),
        "origin": origin,
        "path": stored_path,
        "sha256": digest,
        "media_type": media_type,
        "status": "pending_review",
    }
    if extra:
        entity.update(extra)
    manifest_path = base / "manifest.json"
    manifest = json_read(manifest_path, {"schema_version": 1, "date": chosen_day, "entities": []})
    manifest.setdefault("entities", []).append(entity)
    json_write(manifest_path, manifest)
    record = {
        "schema_version": 1,
        "id": identifier,
        "kind": "source",
        "status": "captured",
        "text": title,
        "date": chosen_day,
        "created_at": now_utc(),
        "created_by": "capture",
        "source_ids": [],
        "related_ids": [],
        "metadata": entity,
    }
    append_record(root, record)
    return record


def latest_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in records}


def projected_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply append-only lifecycle events without changing the historical ledger."""
    projected = [dict(item) for item in records]
    by_id = latest_by_id(projected)
    for event in records:
        metadata = event.get("metadata", {})
        if metadata.get("action") != "set_status":
            continue
        target = by_id.get(str(metadata.get("target_id")))
        if target:
            target["status"] = metadata.get("new_status", target.get("status"))
            target["updated_at"] = event.get("created_at")
            target["updated_by_record"] = event.get("id")
    return projected


def render_table(records: list[dict[str, Any]], empty: str) -> str:
    if not records:
        return empty + "\n"
    lines = ["| ID | Status | Date | Owner | Record |", "|---|---|---|---|---|"]
    for item in records:
        text = str(item.get("text", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{item.get('id')}` | {item.get('status')} | {item.get('date')} | "
            f"{item.get('created_by', 'unknown')} | {text} |"
        )
    return "\n".join(lines) + "\n"


def current_records(records: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    inactive = {"done", "cancelled", "superseded"}
    return [item for item in records if item.get("kind") == kind and item.get("status") not in inactive]


def rebuild(root: Path) -> None:
    historical = read_records(root)
    records = projected_records(historical)
    root.mkdir(parents=True, exist_ok=True)
    registry = root / "registry"
    registry.mkdir(exist_ok=True)
    tasks = current_records(records, "task")
    goals = current_records(records, "goal")
    decisions = [item for item in records if item.get("kind") == "decision"]
    sources = [item for item in records if item.get("kind") == "source"]
    json_write(registry / "catalog.json", {"schema_version": 1, "generated_at": now_utc(), "records": records})
    atomic_write(registry / "tasks.md", "# Active tasks\n\n" + render_table(tasks, "No active tasks."))
    atomic_write(registry / "goals.md", "# Active goals\n\n" + render_table(goals, "No active goals."))
    atomic_write(registry / "decisions.md", "# Decision log\n\n" + render_table(decisions, "No decisions recorded."))
    atomic_write(registry / "sources.md", "# Source catalog\n\n" + render_table(sources, "No sources recorded."))

    recorded_days = {str(item.get("date")) for item in records if item.get("date")}
    existing_days = {path.name for path in (root / "days").glob("*/*/*") if path.is_dir()}
    day_names = sorted(recorded_days | existing_days)
    for day in day_names:
        base = ensure_day(root, day)
        items = [item for item in records if item.get("date") == day]
        pending = [item for item in items if item.get("kind") == "source" and item.get("status") == "captured"]
        content = [
            f"# {day}\n",
            "This index is generated. Start here, then open only the records and artifacts you need.\n",
            "## Navigation\n",
            "- [Daily summary](derived/summary.md)",
            "- [Append-only record ledger](records.ndjson)",
            "- [Source and artifact manifest](manifest.json)",
            "- `raw/` — private source captures; ignored by Git by default",
            "- `work/` — retained work products\n",
            f"## Record counts\n\n- Total: {len(items)}\n- Pending sources: {len(pending)}\n",
            "## Records\n",
            render_table(items, "No records for this day."),
        ]
        atomic_write(base / "INDEX.md", "\n".join(content))

    latest = day_names[-1] if day_names else local_day()
    active_lines = render_table(tasks[:10], "No active tasks.")
    goal_lines = render_table(goals[:5], "No active goals.")
    blocked = [item for item in tasks if item.get("status") in {"blocked", "waiting"}]
    context = f"""# Current context

Generated from canonical records. Keep this file bounded; history belongs in day and week folders.

- **Latest day:** [{latest}](days/{latest[:4]}/{latest[5:7]}/{latest}/INDEX.md)
- **Current week:** `{week_name(latest)}`
- **Last rebuilt:** {now_utc()}

## Active goals

{goal_lines}
## Next actions

{active_lines}
## Blocked or waiting

{render_table(blocked[:10], "Nothing blocked or waiting.")}
## Where to go next

1. Open the latest day index.
2. Use `daily-context trace <ID>` for provenance.
3. Use semantic search only when the deterministic indexes do not answer the question.
"""
    atomic_write(root / "CONTEXT.md", context)


def day_summary_template(day: str) -> str:
    return f"""# Daily summary — {day}

> Derived view. Every material statement should cite a stable record ID.

## Outcome

What changed and why it matters.

## Completed

- None yet.

## Decisions

- None yet.

## Evidence and learning

- None yet.

## Open, blocked, and waiting

- None yet.

## Handoff

The next concrete action.
"""


def init_context(args: argparse.Namespace) -> None:
    root = Path(args.path).expanduser().resolve()
    if (root / CONFIG_NAME).exists():
        raise ContextError(f"Daily Context already exists at {root}")
    root.mkdir(parents=True, exist_ok=True)
    for folder in ("registry", "decisions", "days", "weeks", "inbox", "schemas"):
        (root / folder).mkdir(exist_ok=True)
    config = {
        "schema_version": 1,
        "name": args.name,
        "profile": args.profile,
        "workstreams": args.workstream or [],
        "timezone": args.timezone,
        "week_start": "monday",
        "created_at": now_utc(),
        "auto_update": {
            "mode": args.auto_update,
            "capture_transcript": True,
            "max_transcript_bytes": 5_000_000,
        },
        "privacy": {
            "raw_default": "private",
            "raw_gitignored": True,
            "retention_days": None,
        },
    }
    json_write(root / CONFIG_NAME, config)
    atomic_write(
        root / ".gitignore",
        "# Private evidence and local state\n"
        "days/**/raw/\n"
        "inbox/private/\n"
        ".daily-context.lock\n"
        "*.local.json\n",
    )
    atomic_write(root / "README.md", f"# {args.name}\n\nStart with [CONTEXT.md](CONTEXT.md).\n")
    focus = "\n".join(f"- {item}" for item in PROFILE_HINTS[args.profile])
    streams = "\n".join(f"- {item}" for item in (args.workstream or [])) or "- Add the workstreams that matter here."
    atomic_write(
        root / "PROFILE.md",
        f"# Work profile\n\n"
        f"Profile: **{args.profile}**\n\n"
        "This file guides synthesis without changing the provenance model. Edit it to match the work.\n\n"
        f"## Suggested focus\n\n{focus}\n\n"
        f"## Workstreams\n\n{streams}\n\n"
        "## Vocabulary and success signals\n\n- Define terms, outcomes, and review expectations specific to this work.\n",
    )
    chosen_day = args.date or local_day()
    ensure_day(root, chosen_day)
    if args.goal:
        add_record(root, "goal", args.goal, "accepted", owner=args.owner, day=chosen_day)
    rebuild(root)
    if args.workspace:
        write_pointer(Path(args.workspace).expanduser().resolve(), root)
    print(root)


def write_pointer(workspace: Path, root: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        relative = os.path.relpath(root, workspace)
    except ValueError:
        relative = str(root)
    json_write(workspace / POINTER_NAME, {"schema_version": 1, "path": relative})


def parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def command_record(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    with workspace_lock(root):
        item = add_record(
            root, args.kind, args.text, args.status, parse_csv(args.sources), args.owner,
            args.date, parse_csv(args.related),
        )
        rebuild(root)
    print(item["id"])


def command_source(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    source = Path(args.file) if args.file else None
    with workspace_lock(root):
        item = register_source(
            root, source, args.title or (source.name if source else "Captured note"),
            args.kind, args.sensitivity, not args.reference_only, args.date,
        )
        rebuild(root)
    print(item["id"])


def command_status(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    records = projected_records(read_records(root))
    result = {
        "root": str(root),
        "records": len(records),
        "active_tasks": len(current_records(records, "task")),
        "active_goals": len(current_records(records, "goal")),
        "decisions": sum(1 for item in records if item.get("kind") == "decision"),
        "pending_sources": sum(1 for item in records if item.get("kind") == "source" and item.get("status") == "captured"),
        "auto_update": load_config(root).get("auto_update", {}).get("mode", "off"),
    }
    print(json.dumps(result, indent=2))


def command_rebuild(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    with workspace_lock(root):
        rebuild(root)
    print(f"Rebuilt indexes in {root}")


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    config = load_config(root)
    if config.get("schema_version") != 1:
        errors.append("context.config.json: unsupported schema_version")
    try:
        records = read_records(root)
    except ContextError as exc:
        return [str(exc)]
    identifiers = {str(item.get("id")) for item in records}
    seen: set[str] = set()
    for item in records:
        identifier = str(item.get("id", ""))
        if not identifier:
            errors.append(f"{item.get('_ledger')}: record missing id")
        elif identifier in seen:
            errors.append(f"duplicate record id: {identifier}")
        seen.add(identifier)
        if item.get("kind") not in KINDS | {"source"}:
            errors.append(f"{identifier}: unknown kind {item.get('kind')}")
        if item.get("status") not in STATUSES:
            errors.append(f"{identifier}: unknown status {item.get('status')}")
        for source_id in item.get("source_ids", []):
            if source_id not in identifiers:
                errors.append(f"{identifier}: missing source {source_id}")
    return errors


def command_validate(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    errors = validate(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Valid: {root}")


def command_trace(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    records = projected_records(read_records(root))
    by_id = latest_by_id(records)
    if args.id not in by_id:
        raise ContextError(f"Unknown record ID: {args.id}")
    seen: set[str] = set()

    def walk(identifier: str, depth: int) -> None:
        if identifier in seen:
            print("  " * depth + f"↳ {identifier} (already shown)")
            return
        seen.add(identifier)
        item = by_id.get(identifier)
        if not item:
            print("  " * depth + f"? {identifier} (missing)")
            return
        print("  " * depth + f"{identifier} [{item.get('status')}] {item.get('text')}")
        links = list(item.get("source_ids", [])) + list(item.get("related_ids", []))
        for linked in links:
            walk(str(linked), depth + 1)

    walk(args.id, 0)


def command_weekly(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    chosen_week = args.week or week_name(args.date)
    records = projected_records(read_records(root))
    week_records = [item for item in records if week_name(str(item.get("date"))) == chosen_week]
    week_dir = root / "weeks" / chosen_week
    week_dir.mkdir(parents=True, exist_ok=True)
    source_ids = [item["id"] for item in week_records]
    json_write(
        week_dir / "source-manifest.json",
        {"schema_version": 1, "week": chosen_week, "generated_at": now_utc(), "record_ids": source_ids},
    )
    synthesis = week_dir / "synthesis.md"
    if not synthesis.exists() or args.force:
        atomic_write(synthesis, weekly_template(chosen_week, week_records))
    next_week = week_dir / "next-week.md"
    if not next_week.exists() or args.force:
        open_tasks = current_records(records, "task")
        atomic_write(next_week, next_week_template(chosen_week, open_tasks))
    atomic_write(
        week_dir / "INDEX.md",
        f"# {chosen_week}\n\n- [Weekly synthesis](synthesis.md)\n"
        "- [Next-week plan](next-week.md)\n- [Frozen source manifest](source-manifest.json)\n",
    )
    print(week_dir)


def weekly_template(week: str, records: list[dict[str, Any]]) -> str:
    ids = ", ".join(f"`{item['id']}`" for item in records) or "None"
    return f"""# Weekly synthesis — {week}

> Derived view. Source set frozen in `source-manifest.json`.

## Executive summary

What changed this week and why it matters.

## Progress against goals

- Cite goal, fact, and artifact IDs.

## Outcomes and work products

- Cite record IDs rather than copying daily detail.

## Decisions and changed assumptions

- Include rationale and supersession links.

## Open, blocked, and waiting

- Reconcile every active task with an owner and next action.

## Reflection

- What worked?
- What created avoidable friction?
- What should change next week?

## Source records

{ids}
"""


def next_week_template(week: str, tasks: list[dict[str, Any]]) -> str:
    task_lines = "\n".join(f"- [ ] `{item['id']}` — {item['text']}" for item in tasks) or "- No open tasks."
    return f"""# Next-week plan — after {week}

## Goal

Name the outcome this plan advances.

## Ordered priorities

Explain the ordering rule, then list the smallest useful next actions.

{task_lines}

## Waiting and delegated

- Record owner and follow-up date.

## Deliberately deferred

- State what will not be done and why.
"""


def capture_session(args: argparse.Namespace) -> None:
    try:
        payload = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except json.JSONDecodeError:
        payload = {}
    start = payload.get("cwd") or payload.get("workspace") or os.getcwd()
    try:
        root = find_root(start=start, explicit=args.context)
    except ContextError:
        return
    config = load_config(root)
    auto = config.get("auto_update", {})
    if auto.get("mode") != "capture":
        return
    session_id = str(payload.get("session_id") or payload.get("sessionId") or payload.get("conversation_id") or "unknown")
    transcript_value = payload.get("transcript_path") or payload.get("transcriptPath")
    transcript = Path(str(transcript_value)).expanduser() if transcript_value else None
    capture_key = hashlib.sha256(
        f"{args.host}:{session_id}:{transcript_value or ''}".encode("utf-8")
    ).hexdigest()
    existing = read_records(root)
    if any(item.get("metadata", {}).get("capture_key") == capture_key for item in existing):
        return
    max_bytes = int(auto.get("max_transcript_bytes", 5_000_000))
    can_copy = bool(auto.get("capture_transcript", True)) and transcript and transcript.is_file()
    if can_copy and transcript.stat().st_size > max_bytes:
        can_copy = False
    minimal = {
        "host": args.host,
        "session_id": session_id,
        "cwd": str(start),
        "reason": payload.get("reason"),
        "captured_at": now_utc(),
        "transcript_path": str(transcript) if transcript else None,
    }
    with workspace_lock(root):
        day = local_day()
        base = ensure_day(root, day)
        receipt = base / "raw" / f"session-{slug(args.host)}-{slug(session_id)}.json"
        json_write(receipt, minimal)
        item = register_source(
            root,
            transcript if transcript and transcript.is_file() else receipt,
            f"{args.host.title()} AI session",
            "ai-session",
            "private",
            bool(can_copy),
            day,
            {"capture_key": capture_key, "receipt_path": str(receipt.relative_to(root))},
        )
        rebuild(root)
    print(item["id"])


def command_set_status(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    records = read_records(root)
    target = latest_by_id(records).get(args.id)
    if not target:
        raise ContextError(f"Unknown record ID: {args.id}")
    with workspace_lock(root):
        event = add_record(
            root,
            "activity",
            f"Set {args.id} status to {args.status}",
            "captured",
            owner=args.owner,
            day=args.date,
            related=[args.id],
            metadata={"action": "set_status", "target_id": args.id, "new_status": args.status},
        )
        rebuild(root)
    print(event["id"])


def merge_hook(path: Path, event: str, command: str) -> None:
    data = json_read(path, {}) if path.exists() else {}
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    hooks = data.setdefault("hooks", {})
    entries = hooks.setdefault(event, [])
    for group in entries:
        for hook in group.get("hooks", []):
            if hook.get("command") == command:
                json_write(path, data)
                return
    entries.append({"hooks": [{"type": "command", "command": command, "timeout": 10}]})
    json_write(path, data)


def command_auto(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    workspace = Path(args.workspace or os.getcwd()).expanduser().resolve()
    config = load_config(root)
    config.setdefault("auto_update", {})["mode"] = "capture" if args.action == "enable" else "off"
    json_write(root / CONFIG_NAME, config)
    write_pointer(workspace, root)
    if args.action == "enable":
        command = f"daily-context capture-session --host {args.host}"
        if args.host == "codex":
            merge_hook(workspace / ".codex" / "hooks.json", "SessionEnd", command)
        else:
            merge_hook(workspace / ".claude" / "settings.json", "SessionEnd", command)
    print(f"Auto update {args.action}d for {args.host} in {workspace}")


def command_config(args: argparse.Namespace) -> None:
    root = find_root(explicit=args.context)
    config = load_config(root)
    if args.auto_update:
        config.setdefault("auto_update", {})["mode"] = args.auto_update
        json_write(root / CONFIG_NAME, config)
    print(json.dumps(config, indent=2))


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--context", help="Path to an existing Daily Context")
    top = argparse.ArgumentParser(prog="daily-context", description=__doc__)
    top.add_argument("--version", action="version", version=VERSION)
    sub = top.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a Daily Context workspace")
    init.add_argument("path")
    init.add_argument("--name", default="Daily Context")
    init.add_argument("--profile", choices=("general", "engineering", "research", "operations"), default="general")
    init.add_argument("--timezone", default="local")
    init.add_argument("--goal")
    init.add_argument("--workstream", action="append", help="Add a named workstream; repeat as needed")
    init.add_argument("--owner", default="user")
    init.add_argument("--date")
    init.add_argument("--auto-update", choices=("off", "capture"), default="off")
    init.add_argument("--workspace", help="Write a pointer in this workspace")
    init.set_defaults(func=init_context)

    record = sub.add_parser("record", parents=[common], help="Append a sourced record")
    record.add_argument("kind", choices=sorted(KINDS))
    record.add_argument("text")
    record.add_argument("--status", choices=sorted(STATUSES), default="reported")
    record.add_argument("--sources", help="Comma-separated source IDs")
    record.add_argument("--related", help="Comma-separated related IDs")
    record.add_argument("--owner", default="user")
    record.add_argument("--date")
    record.set_defaults(func=command_record)

    source = sub.add_parser("add-source", parents=[common], help="Register source evidence")
    source.add_argument("file", nargs="?")
    source.add_argument("--title")
    source.add_argument("--kind", default="note")
    source.add_argument("--sensitivity", choices=("public", "internal", "private", "restricted"), default="private")
    source.add_argument("--reference-only", action="store_true")
    source.add_argument("--date")
    source.set_defaults(func=command_source)

    for name, function, help_text in (
        ("status", command_status, "Show current record counts"),
        ("rebuild", command_rebuild, "Regenerate indexes and current context"),
        ("validate", command_validate, "Validate records and references"),
    ):
        item = sub.add_parser(name, parents=[common], help=help_text)
        item.set_defaults(func=function)

    trace = sub.add_parser("trace", parents=[common], help="Trace a record to its sources")
    trace.add_argument("id")
    trace.set_defaults(func=command_trace)

    set_status = sub.add_parser("set-status", parents=[common], help="Append a lifecycle status change")
    set_status.add_argument("id")
    set_status.add_argument("status", choices=sorted(STATUSES))
    set_status.add_argument("--owner", default="user")
    set_status.add_argument("--date")
    set_status.set_defaults(func=command_set_status)

    weekly = sub.add_parser("weekly", parents=[common], help="Create a weekly synthesis workspace")
    weekly.add_argument("--week")
    weekly.add_argument("--date")
    weekly.add_argument("--force", action="store_true")
    weekly.set_defaults(func=command_weekly)

    capture = sub.add_parser("capture-session", parents=[common], help="Capture an AI session from hook JSON")
    capture.add_argument("--host", choices=("codex", "claude", "other"), default="other")
    capture.set_defaults(func=capture_session)

    auto = sub.add_parser("auto", parents=[common], help="Enable or disable safe automatic session capture")
    auto.add_argument("action", choices=("enable", "disable"))
    auto.add_argument("--host", choices=("codex", "claude"), required=True)
    auto.add_argument("--workspace")
    auto.set_defaults(func=command_auto)

    config = sub.add_parser("config", parents=[common], help="Read or update configuration")
    config.add_argument("--auto-update", choices=("off", "capture"))
    config.set_defaults(func=command_config)
    return top


def main() -> int:
    try:
        args = parser().parse_args()
        args.func(args)
        return 0
    except ContextError as exc:
        print(f"daily-context: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

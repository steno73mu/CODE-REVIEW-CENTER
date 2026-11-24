from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import uuid

from .configuration import ScannerConfigStore, ScannerProfile
from .application import scan_project
from .projects import ProjectRegistry
from .storage import ScanStore


def data_directory() -> Path:
    override = os.environ.get("CODE_REVIEW_CENTER_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "code-review-center"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crc",
        description="Local-first multi-engine code review workspace.",
    )
    sub = parser.add_subparsers(dest="resource", required=True)

    project = sub.add_parser("project", help="manage local source directories")
    project_sub = project.add_subparsers(dest="action", required=True)
    add_project = project_sub.add_parser("add")
    add_project.add_argument("--name", required=True)
    add_project.add_argument("--path", required=True)
    project_sub.add_parser("list")
    remove_project = project_sub.add_parser("remove")
    remove_project.add_argument("project_id")

    scanner = sub.add_parser("scanner", help="manage trusted scanner profiles")
    scanner_sub = scanner.add_subparsers(dest="action", required=True)
    add_scanner = scanner_sub.add_parser("add")
    add_scanner.add_argument("--id", required=True)
    add_scanner.add_argument("--name", required=True)
    add_scanner.add_argument("--parser", choices=sorted(_PARSERS), required=True)
    add_scanner.add_argument("--command-json", required=True)
    add_scanner.add_argument("--exit-codes", default="0")
    add_scanner.add_argument("--timeout", type=float, default=300.0)
    scanner_sub.add_parser("list")
    remove_scanner = scanner_sub.add_parser("remove")
    remove_scanner.add_argument("scanner_id")

    scan = sub.add_parser("scan", help="run all enabled scanners for a registered project")
    scan.add_argument("--project", required=True)
    scan.add_argument("--max-workers", type=int, default=4)

    history = sub.add_parser("history", help="inspect saved scan sessions")
    history_sub = history.add_subparsers(dest="action", required=True)
    history_sub.add_parser("list")
    show = history_sub.add_parser("show")
    show.add_argument("session_id")

    return parser


def _json(data: object) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "review.sqlite3"
    projects = ProjectRegistry(database)
    scanners = ScannerConfigStore(database)
    history = ScanStore(database)

    try:
        if args.resource == "project":
            if args.action == "add":
                _json(asdict(projects.register(args.name, args.path)))
            elif args.action == "list":
                _json([asdict(item) for item in projects.list_projects()])
            else:
                if not projects.remove(args.project_id):
                    raise ValueError(f"unknown project: {args.project_id}")
                _json({"removed": args.project_id})

        elif args.resource == "scanner":
            if args.action == "add":
                try:
                    command = json.loads(args.command_json)
                    exit_codes = tuple(int(item.strip()) for item in args.exit_codes.split(","))
                except (json.JSONDecodeError, ValueError) as exc:
                    raise ValueError("command JSON or exit-code list is invalid") from exc
                profile = ScannerProfile(
                    scanner_id=args.id,
                    name=args.name,
                    parser=args.parser,
                    command=tuple(command) if isinstance(command, list) else command,
                    accepted_exit_codes=exit_codes,
                    timeout_seconds=args.timeout,
                )
                scanners.save(profile)
                _json(asdict(profile))
            elif args.action == "list":
                _json([asdict(item) for item in scanners.list_profiles()])
            else:
                if not scanners.remove(args.scanner_id):
                    raise ValueError(f"unknown scanner: {args.scanner_id}")
                _json({"removed": args.scanner_id})

        elif args.resource == "scan":
            project = projects.get(args.project)
            if project is None:
                raise ValueError(f"unknown project: {args.project}")
            profiles = scanners.list_profiles(enabled_only=True)
            if not profiles:
                raise ValueError("no enabled scanner profiles are configured")
            batch = scan_project(project, profiles, max_workers=args.max_workers)
            session_id = str(uuid.uuid4())
            history.save_batch(session_id, batch)
            _json({
                "session_id": session_id,
                "project_id": project.project_id,
                "project_name": project.name,
                "status": "completed" if all(item.status.value == "succeeded" for item in batch.jobs) else "partial",
                "duration_seconds": batch.duration_seconds,
                "jobs": [
                    {
                        "job_id": item.job_id,
                        "status": item.status.value,
                        "error": item.error,
                        "finding_count": len(item.scan_result.findings) if item.scan_result else 0,
                    }
                    for item in batch.jobs
                ],
                "finding_count": len(batch.findings),
                "findings": [
                    {
                        "tool": finding.tool,
                        "severity": finding.severity.value,
                        "rule_id": finding.rule_id,
                        "message": finding.message,
                        "path": finding.path,
                        "start_line": finding.start_line,
                        "fingerprint": finding.fingerprint,
                    }
                    for finding in batch.findings
                ],
            })
            if not any(item.status.value == "succeeded" for item in batch.jobs):
                return 1

        elif args.resource == "history":
            if args.action == "list":
                _json(history.list_sessions())
            else:
                result = history.get_batch(args.session_id)
                if result is None:
                    raise ValueError(f"unknown scan session: {args.session_id}")
                _json(result)

        return 0
    except (ValueError, TypeError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

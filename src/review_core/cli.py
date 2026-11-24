from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
import platform
from pathlib import Path
import sys
import uuid

from .configuration import ProviderConfigStore, ProviderProfile, ScannerConfigStore, ScannerProfile
from .providers import AIReviewClient, AIReviewError
from .application import scan_project
from .projects import ProjectRegistry
from .storage import ScanStore
from .finding import Finding
from .reports import render_report, write_report
from .triage import TriageStore, TriageStatus


def data_directory() -> Path:
    override = os.environ.get("CODE_REVIEW_CENTER_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "code-review-center"


def ensure_data_directory() -> Path:
    directory = data_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        directory.chmod(0o700)
    return directory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crc",
        description="Local-first multi-engine code review workspace.",
    )
    sub = parser.add_subparsers(dest="resource", required=True)

    sub.add_parser("doctor", help="check local runtime and configured scanner availability (offline)")

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
    add_scanner.add_argument("--parser", choices=("semgrep", "gitleaks", "sarif"), required=True)
    add_scanner.add_argument("--command-json", required=True)
    add_scanner.add_argument("--exit-codes", default="0")
    add_scanner.add_argument("--timeout", type=float, default=300.0)
    scanner_sub.add_parser("list")
    preset = scanner_sub.add_parser("preset")
    preset_sub = preset.add_subparsers(dest="preset_action", required=True)
    preset_sub.add_parser("list")
    preset_add = preset_sub.add_parser("add")
    preset_add.add_argument("preset_name", choices=("semgrep", "gitleaks"))

    remove_scanner = scanner_sub.add_parser("remove")
    remove_scanner.add_argument("scanner_id")

    provider = sub.add_parser("provider", help="manage OpenAI-compatible AI reviewers")
    provider_sub = provider.add_subparsers(dest="action", required=True)
    add_provider = provider_sub.add_parser("add")
    add_provider.add_argument("--id", required=True)
    add_provider.add_argument("--name", required=True)
    add_provider.add_argument("--url", required=True)
    add_provider.add_argument("--model", required=True)
    add_provider.add_argument("--api-key-env")
    add_provider.add_argument("--timeout", type=float, default=60.0)
    provider_sub.add_parser("list")
    remove_provider = provider_sub.add_parser("remove")
    remove_provider.add_argument("provider_id")

    review = sub.add_parser("review", help="ask a configured AI provider to review saved findings")
    review.add_argument("--session", required=True)
    review.add_argument("--provider", required=True)
    review.add_argument("--allow-external", action="store_true")

    scan = sub.add_parser("scan", help="run all enabled scanners for a registered project")
    scan.add_argument("--project", required=True)
    scan.add_argument("--max-workers", type=int, default=4)

    triage = sub.add_parser("triage", help="set or inspect finding disposition")
    triage_sub = triage.add_subparsers(dest="action", required=True)
    triage_list = triage_sub.add_parser("list")
    triage_list.add_argument("--session", required=True)
    triage_set = triage_sub.add_parser("set")
    triage_set.add_argument("--session", required=True)
    triage_set.add_argument("--fingerprint", required=True)
    triage_set.add_argument("--status", choices=tuple(item.value for item in TriageStatus), required=True)
    triage_set.add_argument("--note", default=None)

    report = sub.add_parser("report", help="export a saved scan as JSON, SARIF, or Markdown")
    report.add_argument("--session", required=True)
    report.add_argument("--format", choices=("json", "sarif", "markdown"), required=True)
    report.add_argument("--output", required=True)
    report.add_argument("--force", action="store_true", help="replace an existing output file")

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
    directory = ensure_data_directory()
    database = directory / "review.sqlite3"
    projects = ProjectRegistry(database)
    scanners = ScannerConfigStore(database)
    providers = ProviderConfigStore(database)
    history = ScanStore(database)
    triage_store = TriageStore(database)

    try:
        if args.resource == "doctor":
            import importlib.util
            import shutil
            import sqlite3
            python_ok = sys.version_info >= (3, 11)
            scanner_checks = []
            for profile in scanners.list_profiles(enabled_only=True):
                executable = profile.command[0]
                available = shutil.which(executable) is not None or Path(executable).is_file()
                scanner_checks.append({
                    "id": profile.scanner_id, "executable": executable, "available": available,
                })
            provider_checks = [
                {
                    "id": profile.provider_id,
                    "enabled": profile.enabled,
                    "api_key_env_configured": bool(profile.api_key_env),
                    "api_key_present": bool(os.environ.get(profile.api_key_env)) if profile.api_key_env else False,
                }
                for profile in providers.list_profiles()
            ]
            checks = {
                "python": {"ok": python_ok, "version": platform.python_version()},
                "sqlite": {"ok": True, "version": sqlite3.sqlite_version},
                "desktop": {"available": importlib.util.find_spec("tkinter") is not None, "required": False},
                "application_data": {
                    "path": str(directory),
                    "private": os.name == "nt" or (directory.stat().st_mode & 0o777) == 0o700,
                },
                "scanners": scanner_checks,
                "providers": provider_checks,
            }
            ok = python_ok and all(item["available"] for item in scanner_checks)
            checks["application_data"]["ok"] = checks["application_data"]["private"]
            checks["ok"] = ok and checks["application_data"]["ok"]
            _json({"ok": checks["ok"], "checks": checks})
            return 0 if checks["ok"] else 1
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
            elif args.action == "preset":
                if args.preset_action == "list":
                    _json([
                        {"name": "semgrep", "parser": "semgrep", "executable": "semgrep"},
                        {"name": "gitleaks", "parser": "gitleaks", "executable": "gitleaks"},
                    ])
                else:
                    if args.preset_name == "semgrep":
                        profile = ScannerProfile(
                            scanner_id="semgrep-default", name="Semgrep", parser="semgrep",
                            command=("semgrep", "scan", "--config", "auto", "--json", "--quiet", "{project_path}"),
                            accepted_exit_codes=(0,), timeout_seconds=300.0,
                        )
                    else:
                        profile = ScannerProfile(
                            scanner_id="gitleaks-default", name="Gitleaks", parser="gitleaks",
                            command=("gitleaks", "dir", "--report-format", "json", "--report-path", "-", "--redact=100", "--no-banner", "--no-color", "--log-level", "fatal", "{project_path}"),
                            accepted_exit_codes=(0, 1), timeout_seconds=300.0,
                        )
                    scanners.save(profile)
                    _json(asdict(profile))
            else:
                if not scanners.remove(args.scanner_id):
                    raise ValueError(f"unknown scanner: {args.scanner_id}")
                _json({"removed": args.scanner_id})

        elif args.resource == "provider":
            if args.action == "add":
                profile = ProviderProfile(
                    provider_id=args.id, name=args.name, base_url=args.url,
                    model=args.model, api_key_env=args.api_key_env,
                    timeout_seconds=args.timeout,
                )
                providers.save(profile)
                _json(asdict(profile))
            elif args.action == "list":
                _json([asdict(item) for item in providers.list_profiles()])
            else:
                if not providers.remove(args.provider_id):
                    raise ValueError(f"unknown provider: {args.provider_id}")
                _json({"removed": args.provider_id})

        elif args.resource == "review":
            provider = providers.get(args.provider)
            if provider is None:
                raise ValueError(f"unknown provider: {args.provider}")
            session = history.get_batch(args.session)
            if session is None:
                raise ValueError(f"unknown scan session: {args.session}")
            findings = [Finding(**item) for item in session["findings"]]
            result = AIReviewClient().review_findings(
                provider, findings, allow_external=args.allow_external
            )
            review_id = history.save_ai_review(args.session, result)
            _json({
                "provider_id": result.provider_id,
                "model": result.model,
                "session_id": args.session,
                "review_id": review_id,
                "finding_count": len(findings),
                "review": result.content,
            })

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
                "correlation_group_count": len(batch.correlations),
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

        elif args.resource == "triage":
            if args.action == "list":
                _json(triage_store.list_for_session(args.session))
            else:
                _json(triage_store.set_status(args.session, args.fingerprint, args.status, note=args.note))

        elif args.resource == "report":
            session = history.get_batch(args.session)
            if session is None:
                raise ValueError(f"unknown scan session: {args.session}")
            session["triage"] = triage_store.list_for_session(args.session)
            rendered = render_report(session, args.format)
            target = write_report(args.output, rendered, overwrite=args.force)
            _json({"session_id": args.session, "format": args.format, "path": str(target)})

        elif args.resource == "history":
            if args.action == "list":
                _json(history.list_sessions())
            else:
                result = history.get_batch(args.session_id)
                if result is None:
                    raise ValueError(f"unknown scan session: {args.session_id}")
                result["triage"] = triage_store.list_for_session(args.session_id)
                _json(result)

        return 0
    except (AIReviewError, ValueError, TypeError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

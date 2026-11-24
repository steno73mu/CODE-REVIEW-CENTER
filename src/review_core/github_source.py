from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse
import uuid


def validate_github_url(url: str) -> str:
    if not isinstance(url, str):
        raise ValueError("GitHub repository URL must be text")
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password:
        raise ValueError("use an HTTPS URL from github.com, for example https://github.com/owner/repository")
    parts = [part for part in parsed.path.strip("/").removesuffix(".git").split("/") if part]
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise ValueError("GitHub URL must point to a repository: https://github.com/owner/repository")
    return f"https://github.com/{parts[0]}/{parts[1]}.git"


def clone_github_repository(url: str, destination_root: str | Path, *, branch: str | None = None) -> Path:
    """Clone a GitHub repository as data; never execute repository code."""
    repository_url = validate_github_url(url)
    if branch is not None and (not branch.strip() or branch.startswith("-") or any(char in branch for char in "\0\r\n")):
        raise ValueError("branch name is invalid")
    root = Path(destination_root).expanduser()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        root.chmod(0o700)
    destination = root / str(uuid.uuid4())
    command = ["git", "clone", "--depth", "1", "--single-branch"]
    if branch:
        command.extend(["--branch", branch.strip()])
    command.extend(["--", repository_url, str(destination)])
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=180, check=False, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"GitHub clone failed: {exc}") from exc
    if result.returncode:
        destination.exists() and __import__("shutil").rmtree(destination, ignore_errors=True)
        detail = result.stderr.strip()[-1000:] or "git clone returned an error"
        raise ValueError(f"GitHub clone failed: {detail}")
    return destination

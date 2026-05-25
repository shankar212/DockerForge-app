from __future__ import annotations

import re
import shutil
import stat
import time
from pathlib import Path
from urllib.parse import urlparse

from git import Repo


GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$"
)


def _repo_folder_name(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL.")
    owner, repo = parts[0], parts[1].replace(".git", "")
    return f"{owner}__{repo}"


def validate_github_url(repo_url: str) -> str:
    cleaned_url = repo_url.strip().removesuffix(".git").rstrip("/")
    if not GITHUB_URL_PATTERN.match(cleaned_url):
        raise ValueError("Enter a public GitHub HTTPS URL like https://github.com/owner/repo")
    return cleaned_url


def _handle_remove_readonly(func, path, _exc_info) -> None:
    Path(path).chmod(stat.S_IWRITE)
    func(path)


def _remove_existing_repo(path: Path) -> bool:
    for _attempt in range(3):
        try:
            shutil.rmtree(path, onerror=_handle_remove_readonly)
            return True
        except PermissionError:
            time.sleep(1)
        except OSError:
            time.sleep(1)
    return False


def clone_repository(repo_url: str, repos_dir: str | Path = "repos") -> Path:
    """Clone a public GitHub repository into repos/ and return the local path."""
    cleaned_url = validate_github_url(repo_url)
    target_root = Path(repos_dir)
    target_root.mkdir(parents=True, exist_ok=True)

    destination = target_root / _repo_folder_name(cleaned_url)
    if destination.exists():
        removed = _remove_existing_repo(destination)
        if not removed:
            destination = target_root / f"{_repo_folder_name(cleaned_url)}__{int(time.time())}"

    try:
        Repo.clone_from(cleaned_url, destination, depth=1)
    except Exception as exc:
        raise RuntimeError(f"Failed to clone repository: {exc}") from exc

    return destination.resolve()

from __future__ import annotations

import subprocess
import time
from collections.abc import Mapping


def _run(command: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _combined_output(process: subprocess.CompletedProcess[str]) -> str:
    return f"{process.stdout or ''}\n{process.stderr or ''}".strip()


def run_container(
    image_tag: str,
    wait_seconds: int = 8,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Start the generated image and verify the container stays alive briefly."""
    container_name = f"{image_tag.replace(':', '-').replace('/', '-')}-run"
    env_args: list[str] = []
    for key, value in (env or {}).items():
        env_args.extend(["-e", f"{key}={value}"])

    try:
        _run(["docker", "rm", "-f", container_name], timeout=30)
        start = _run(
            ["docker", "run", "-d", "--name", container_name, "-P", *env_args, image_tag],
            timeout=60,
        )
    except FileNotFoundError:
        return {
            "success": False,
            "container_name": container_name,
            "logs": "Docker executable was not found. Install Docker Desktop and ensure docker is on PATH.",
            "ports": "",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "container_name": container_name,
            "logs": "Docker did not respond before the container startup timeout.",
            "ports": "",
        }

    if start.returncode != 0:
        return {
            "success": False,
            "container_name": container_name,
            "logs": _combined_output(start),
            "ports": "",
        }

    time.sleep(wait_seconds)
    try:
        inspect = _run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            timeout=30,
        )
        logs = _run(["docker", "logs", container_name], timeout=30)
        ports = _run(["docker", "port", container_name], timeout=30)
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "container_name": container_name,
            "logs": "Docker did not respond while checking the container status.",
            "ports": "",
        }

    is_running = (inspect.stdout or "").strip().lower() == "true"
    return {
        "success": is_running,
        "container_name": container_name,
        "logs": _combined_output(logs),
        "ports": (ports.stdout or "").strip(),
    }

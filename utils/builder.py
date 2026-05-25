from __future__ import annotations

import subprocess
import time
from pathlib import Path


def check_docker_available(timeout_seconds: int = 20) -> tuple[bool, str]:
    try:
        process = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return False, "Docker executable was not found. Install Docker Desktop and ensure docker is on PATH."
    except subprocess.TimeoutExpired:
        return False, "Docker did not respond in time. Start or restart Docker Desktop."

    output = (process.stdout or "") + "\n" + (process.stderr or "")
    if process.returncode != 0:
        return False, output.strip() or "Docker Desktop is not reachable."
    return True, output.strip()


def build_image(
    repo_path: str | Path,
    dockerfile_path: str | Path = "generated/Dockerfile",
    image_tag: str | None = None,
    logs_path: str | Path = "generated/build_logs.txt",
    timeout_seconds: int = 600,
) -> dict[str, object]:
    """Run docker build and capture stdout/stderr without invoking a shell."""
    repo = Path(repo_path).resolve()
    dockerfile = Path(dockerfile_path).resolve()
    logs = Path(logs_path)
    logs.parent.mkdir(parents=True, exist_ok=True)

    if not repo.exists():
        raise FileNotFoundError(f"Build context not found: {repo}")
    if not dockerfile.exists():
        raise FileNotFoundError(f"Dockerfile not found: {dockerfile}")

    tag = image_tag or f"dockerforge-ai-{repo.name.lower().replace('_', '-')}-{int(time.time())}"
    command = ["docker", "build", "-f", str(dockerfile), "-t", tag, str(repo)]

    docker_ok, docker_message = check_docker_available()
    if not docker_ok:
        logs.write_text(docker_message, encoding="utf-8")
        return {
            "success": False,
            "image_tag": tag,
            "logs": docker_message,
            "returncode": 125,
            "infrastructure_error": True,
        }

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        combined = (exc.stdout or "") + "\n" + (exc.stderr or "")
        logs.write_text(combined + "\nBuild timed out.", encoding="utf-8")
        return {"success": False, "image_tag": tag, "logs": combined, "returncode": 124}
    except FileNotFoundError as exc:
        message = "Docker executable was not found. Install Docker Desktop and ensure docker is on PATH."
        logs.write_text(message, encoding="utf-8")
        raise RuntimeError(message) from exc

    combined_logs = (process.stdout or "") + "\n" + (process.stderr or "")
    logs.write_text(combined_logs, encoding="utf-8")

    return {
        "success": process.returncode == 0,
        "image_tag": tag,
        "logs": combined_logs,
        "returncode": process.returncode,
        "infrastructure_error": _is_docker_infrastructure_error(combined_logs),
    }


def _is_docker_infrastructure_error(logs: str) -> bool:
    lowered = logs.lower()
    infrastructure_markers = (
        "_ping",
        "dockerdesktoplinuxengine",
        "is the docker daemon running",
        "cannot connect to the docker daemon",
        "internal server error for api route",
        "server supports the requested api version",
    )
    return any(marker in lowered for marker in infrastructure_markers)

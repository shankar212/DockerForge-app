from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from utils.gemini_client import generate_content_with_fallback


def _extract_dockerfile(text: str) -> str:
    match = re.search(r"```(?:dockerfile|Dockerfile)?\s*(.*?)```", text, flags=re.DOTALL)
    dockerfile = match.group(1) if match else text
    dockerfile = dockerfile.strip()
    if not dockerfile.upper().startswith("FROM "):
        from_index = dockerfile.upper().find("FROM ")
        if from_index >= 0:
            dockerfile = dockerfile[from_index:].strip()
    return dockerfile


def fix_dockerfile(
    current_dockerfile: str,
    build_logs: str,
    attempt: int,
    repository_analysis: dict[str, Any] | None = None,
    failure_stage: str = "Docker build",
    max_log_chars: int = 18_000,
) -> str:
    analysis_context = ""
    if repository_analysis:
        analysis_context = f"""
Repository analysis:
{repository_analysis}
""".strip()

    prompt = f"""
You are DockerForge-AI's retry agent.
The {failure_stage} failed on retry attempt {attempt}.

{analysis_context}

Current Dockerfile:
{current_dockerfile}

Failure logs:
{build_logs[-max_log_chars:]}

Return only a corrected Dockerfile. No markdown and no explanation.
Fix the actual failure while keeping the Dockerfile compatible with the same repository build context.
""".strip()

    try:
        response_text, _model_name = generate_content_with_fallback(prompt)
        dockerfile = _extract_dockerfile(response_text)
    except Exception as exc:
        raise RuntimeError(f"Gemini failed to repair Dockerfile: {exc}") from exc

    if not dockerfile:
        raise RuntimeError("Gemini returned an empty corrected Dockerfile.")
    return dockerfile


def read_logs(logs_path: str | Path = "generated/build_logs.txt") -> str:
    path = Path(logs_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")

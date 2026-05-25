from __future__ import annotations

import json
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


def _base_prompt(analysis: dict[str, Any]) -> str:
    return f"""
You are DockerForge-AI, an expert DevOps agent.
Generate one production-ready Dockerfile for the repository analysis below.

Repository analysis JSON:
{json.dumps(analysis, indent=2)}

Rules:
- Return only the Dockerfile content. No markdown, no explanation.
- The Dockerfile will be built with the cloned repository as the build context.
- Prefer small official base images.
- Include system packages only when needed.
- For Python apps, install requirements.txt when present.
- For Streamlit apps, expose port 8501 and use CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"] when app.py exists.
- For Flask/FastAPI apps, expose the most likely app port and provide a valid CMD.
- For Node/React apps, use npm install/npm ci, build when appropriate, and run a sensible production command.
- For Express/API apps, prefer the package.json start script, set a non-secret PORT default when detectable, and expose the detected/default API port.
- Do not bake secret runtime environment values into the image. Document them only through ENV defaults when they are safe non-secret values such as PORT or NODE_ENV.
- For Java Maven projects, build with Maven and run the generated jar when possible.
- Avoid copying files from outside the repository context.
- Make the Dockerfile robust for public starter repositories.
""".strip()


def generate_dockerfile(analysis: dict[str, Any]) -> str:
    try:
        response_text, _model_name = generate_content_with_fallback(_base_prompt(analysis))
        dockerfile = _extract_dockerfile(response_text)
    except Exception as exc:
        raise RuntimeError(f"Gemini failed to generate Dockerfile: {exc}") from exc

    if not dockerfile:
        raise RuntimeError("Gemini returned an empty Dockerfile.")
    return dockerfile


def save_dockerfile(content: str, output_path: str | Path = "generated/Dockerfile") -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path.resolve()

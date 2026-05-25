from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


IMPORTANT_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "package.json",
    "pom.xml",
    "build.gradle",
    "gradlew",
    "app.py",
    "main.py",
    "manage.py",
}


def _safe_read(path: Path, max_chars: int = 12_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""


def _detect_python_framework(repo_path: Path) -> list[str]:
    frameworks: set[str] = set()
    candidates = list(repo_path.rglob("*.py"))[:80]
    for file_path in candidates:
        text = _safe_read(file_path, max_chars=8_000).lower()
        if "from flask" in text or "import flask" in text:
            frameworks.add("Flask")
        if "from fastapi" in text or "import fastapi" in text:
            frameworks.add("FastAPI")
        if "django" in text or "manage.py" in file_path.name:
            frameworks.add("Django")
        if "streamlit" in text:
            frameworks.add("Streamlit")
    return sorted(frameworks)


def _detect_node_frameworks(package_json: Path) -> list[str]:
    frameworks: set[str] = set()
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    dependencies: dict[str, Any] = {}
    dependencies.update(data.get("dependencies", {}))
    dependencies.update(data.get("devDependencies", {}))

    if "react" in dependencies:
        frameworks.add("React")
    if "next" in dependencies:
        frameworks.add("Next.js")
    if "vite" in dependencies:
        frameworks.add("Vite")
    if "express" in dependencies:
        frameworks.add("Express")
    return sorted(frameworks)


def _read_package_metadata(package_json: Path) -> dict[str, Any]:
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return {
        "scripts": data.get("scripts", {}),
        "dependencies": sorted(data.get("dependencies", {}).keys()),
        "devDependencies": sorted(data.get("devDependencies", {}).keys()),
    }


def _detect_runtime_hints(repo_path: Path) -> dict[str, Any]:
    env_vars: set[str] = set()
    ports: set[str] = set()
    env_pattern = re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)")
    fallback_port_pattern = re.compile(r"process\.env\.PORT\s*\|\|\s*['\"]?(\d+)['\"]?")

    for path in list(repo_path.rglob("*.js"))[:120]:
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        text = _safe_read(path, max_chars=12_000)
        env_vars.update(env_pattern.findall(text))
        ports.update(fallback_port_pattern.findall(text))

    render_yaml = repo_path / "render.yaml"
    if render_yaml.exists():
        text = _safe_read(render_yaml)
        env_vars.update(re.findall(r"key:\s*([A-Z][A-Z0-9_]*)", text))
        ports.update(re.findall(r"PORT\s*\n\s*value:\s*[\"']?(\d+)", text))

    readme = repo_path / "README.md"
    if readme.exists():
        text = _safe_read(readme)
        env_vars.update(re.findall(r"\b([A-Z][A-Z0-9_]*)=", text))
        ports.update(re.findall(r"localhost:(\d+)", text))

    return {
        "environment_variables": sorted(env_vars),
        "ports": sorted(ports),
    }


def _find_files(repo_path: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {name: [] for name in IMPORTANT_FILES}
    found["src/"] = []

    for path in repo_path.rglob("*"):
        if ".git" in path.parts:
            continue
        relative = path.relative_to(repo_path).as_posix()
        if path.is_file() and path.name in IMPORTANT_FILES:
            found[path.name].append(relative)
        if path.is_dir() and path.name == "src":
            found["src/"].append(relative + "/")

    return {key: values for key, values in found.items() if values}


def _directory_tree(repo_path: Path, max_entries: int = 160) -> list[str]:
    entries: list[str] = []
    for path in sorted(repo_path.rglob("*")):
        if len(entries) >= max_entries:
            entries.append("... output truncated ...")
            break
        if ".git" in path.parts:
            continue
        relative = path.relative_to(repo_path)
        depth = len(relative.parts)
        if depth > 4:
            continue
        suffix = "/" if path.is_dir() else ""
        entries.append(f"{'  ' * (depth - 1)}{relative.as_posix()}{suffix}")
    return entries


def analyze_repository(repo_path: str | Path) -> dict[str, Any]:
    """Inspect repository files and infer a practical Docker build strategy."""
    root = Path(repo_path)
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")

    files = _find_files(root)
    frameworks = _detect_python_framework(root)
    package_json = root / "package.json"
    package_metadata = {}
    if package_json.exists():
        frameworks.extend(_detect_node_frameworks(package_json))
        package_metadata = _read_package_metadata(package_json)

    tech_stack: set[str] = set()
    if any(key in files for key in ["requirements.txt", "pyproject.toml", "Pipfile", "app.py", "main.py"]):
        tech_stack.add("Python")
    if "package.json" in files:
        tech_stack.add("Node.js")
    if any(key in files for key in ["pom.xml", "build.gradle", "gradlew"]):
        tech_stack.add("Java")
    if "React" in frameworks:
        tech_stack.add("React")

    return {
        "repo_name": root.name,
        "repo_path": str(root.resolve()),
        "detected_files": files,
        "frameworks": sorted(set(frameworks)),
        "tech_stack": sorted(tech_stack) or ["Unknown"],
        "tree": _directory_tree(root),
        "package_json": package_metadata,
        "runtime_hints": _detect_runtime_hints(root),
        "hints": {
            "has_requirements": "requirements.txt" in files,
            "has_package_json": "package.json" in files,
            "has_pom": "pom.xml" in files,
            "has_app_py": "app.py" in files,
            "has_main_py": "main.py" in files,
            "has_src": "src/" in files,
        },
    }

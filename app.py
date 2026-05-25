from __future__ import annotations

from pathlib import Path

import streamlit as st

from utils.analyzer import analyze_repository
from utils.builder import build_image, check_docker_available
from utils.clone_repo import clone_repository
from utils.generator import generate_dockerfile, save_dockerfile
from utils.retry_agent import fix_dockerfile
from utils.runner import run_container


MAX_RETRIES = 3
GENERATED_DOCKERFILE = Path("generated/Dockerfile")


st.set_page_config(page_title="DockerForge-AI", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; max-width: 1180px; }
    .status-box { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("DockerForge-AI")
st.caption("AI-powered Dockerfile generation, build validation, retry repair, and container startup.")

repo_url = st.text_input(
    "Public GitHub repository URL",
    placeholder="https://github.com/owner/repository",
)

run_clicked = st.button("Analyze and Build", type="primary", use_container_width=False)

runtime_env_text = st.text_area(
    "Runtime environment variables",
    placeholder="PORT=5000\nMONGODB_URI=mongodb+srv://user:password@cluster.example.net/fintech\nJWT_SECRET=change-me\nJWT_EXPIRES_IN=1d",
    height=120,
)

status_placeholder = st.empty()
retry_placeholder = st.empty()
logs_placeholder = st.empty()
dockerfile_placeholder = st.empty()


def show_dockerfile(content: str) -> None:
    dockerfile_placeholder.subheader("Generated Dockerfile")
    dockerfile_placeholder.code(content, language="dockerfile")


def parse_runtime_env(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Runtime environment line {line_number} must use KEY=VALUE format.")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Runtime environment line {line_number} has an empty key.")
        env[key] = value.strip().strip('"').strip("'")
    return env


if run_clicked:
    if not repo_url.strip():
        st.error("Enter a GitHub repository URL first.")
        st.stop()

    try:
        runtime_env = parse_runtime_env(runtime_env_text)

        status_placeholder.info("Cloning repository...")
        repo_path = clone_repository(repo_url)

        docker_ok, docker_message = check_docker_available()
        if not docker_ok:
            status_placeholder.error("Docker Desktop is not reachable. Start or restart Docker Desktop, then try again.")
            logs_placeholder.subheader("Docker status")
            logs_placeholder.text_area(
                "Docker status output",
                docker_message,
                height=220,
                key="docker_status_output",
            )
            st.stop()

        status_placeholder.info("Analyzing repository structure and tech stack...")
        analysis = analyze_repository(repo_path)

        with st.expander("Repository analysis", expanded=True):
            st.json(analysis)

        status_placeholder.info("Generating Dockerfile with Gemini...")
        dockerfile_content = generate_dockerfile(analysis)
        save_dockerfile(dockerfile_content, GENERATED_DOCKERFILE)
        show_dockerfile(dockerfile_content)

        image_tag = None
        build_result = None
        for attempt in range(1, MAX_RETRIES + 2):
            retry_placeholder.metric("Build attempt", attempt)
            status_placeholder.info(f"Running docker build, attempt {attempt}...")
            build_result = build_image(
                repo_path=repo_path,
                dockerfile_path=GENERATED_DOCKERFILE,
                image_tag=image_tag,
            )
            image_tag = str(build_result["image_tag"])

            logs = str(build_result.get("logs", ""))
            attempt_logs_path = Path("generated") / f"build_attempt_{attempt}.log"
            attempt_logs_path.write_text(logs, encoding="utf-8")
            logs_placeholder.subheader("Build logs")
            logs_placeholder.text_area(
                "Docker build output",
                logs,
                height=320,
                key=f"docker_build_output_{attempt}",
            )

            if build_result["success"]:
                status_placeholder.success("Docker image built successfully.")
                break

            if build_result.get("infrastructure_error"):
                status_placeholder.error(
                    "Docker Desktop returned an infrastructure error. Restart Docker Desktop and try again."
                )
                st.stop()

            if attempt > MAX_RETRIES:
                status_placeholder.error("Docker build failed after maximum retries.")
                st.stop()

            status_placeholder.warning(
                f"Build failed on attempt {attempt}. Sending Docker error logs to Gemini and regenerating Dockerfile..."
            )
            dockerfile_content = fix_dockerfile(
                current_dockerfile=dockerfile_content,
                build_logs=logs,
                attempt=attempt,
                repository_analysis=analysis,
            )
            save_dockerfile(dockerfile_content, GENERATED_DOCKERFILE)
            show_dockerfile(dockerfile_content)
            status_placeholder.info(f"Retrying automatically with repaired Dockerfile, attempt {attempt + 1}...")

        if not build_result or not build_result["success"]:
            st.error("No successful image was produced.")
            st.stop()

        status_placeholder.info("Starting generated container...")
        run_result = run_container(str(build_result["image_tag"]), env=runtime_env)
        if run_result["success"]:
            status_placeholder.success("Container started successfully.")
            st.write(f"Container: `{run_result['container_name']}`")
            if run_result.get("ports"):
                st.write(f"Published ports: `{run_result['ports']}`")
        else:
            status_placeholder.error("Image built, but the container did not stay running.")

        with st.expander("Container logs", expanded=not run_result["success"]):
            st.text(run_result.get("logs", ""))

        final_dockerfile = GENERATED_DOCKERFILE.read_text(encoding="utf-8")
        show_dockerfile(final_dockerfile)

    except Exception as exc:
        status_placeholder.error(str(exc))

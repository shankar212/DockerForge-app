# DockerForge-AI

DockerForge-AI is an AI-powered Dockerfile generator. It accepts a public GitHub repository URL, clones and analyzes the project, asks Gemini to generate a Dockerfile, validates the Dockerfile with `docker build`, retries with build logs when the build fails, and then starts the generated container.

## Architecture

DockerForge-AI is organized as a Streamlit orchestration layer plus small utility modules for cloning, analysis, LLM generation, Docker build validation, retry repair, and runtime verification.

```text
User enters GitHub URL
        |
        v
Streamlit UI app.py
        |
        v
clone_repo.py clones the public repository into repos/
        |
        v
analyzer.py detects files, frameworks, package scripts, ports, and env hints
        |
        v
generator.py sends repository analysis to Gemini and saves generated/Dockerfile
        |
        v
builder.py runs docker build and captures build logs
        |
        +-- build fails --> retry_agent.py sends logs + Dockerfile to Gemini
        |                  and regenerates Dockerfile, then rebuilds
        |
        v
runner.py starts the built image and checks whether it stays alive
        |
        +-- runtime fails --> retry_agent.py sends container logs to Gemini
        |                    and retries with a corrected Dockerfile
        |
        v
Container success message and logs shown in the UI
```

- `app.py`: Streamlit UI and workflow orchestration.
- `utils/clone_repo.py`: GitHub URL validation and GitPython clone logic.
- `utils/analyzer.py`: Repository structure, file, framework, and stack detection.
- `utils/generator.py`: Gemini prompt and first Dockerfile generation.
- `utils/builder.py`: Safe `subprocess.run` wrapper for `docker build`.
- `utils/retry_agent.py`: Sends the failed Dockerfile and build logs back to Gemini for repair.
- `utils/runner.py`: Starts the built image and verifies that the container stays alive.
- `generated/`: Stores the generated Dockerfile and build logs.
- `repos/`: Stores cloned repositories locally.

## Setup

Prerequisites:

- Python 3.10 or newer.
- Docker Desktop running locally.
- A Google Gemini API key.
- Git installed and available on PATH.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Install Docker Desktop and confirm Docker is available:

```bash
docker --version
```

Create `.env` in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

Run the app:

```bash
streamlit run app.py
```

## Environment Variables

- `GEMINI_API_KEY`: API key used by `google-generativeai`.
- `GEMINI_MODEL`: Preferred Gemini model. Defaults to `gemini-2.5-flash` with automatic fallback.

## LLM Provider

DockerForge-AI uses Google Gemini through the `google-generativeai` Python SDK.

Default model:

```python
genai.GenerativeModel("gemini-2.5-flash")
```

Gemini was selected because it is fast enough for an interactive Streamlit workflow, has strong code-generation ability for Dockerfiles and build-log repair, and supports a practical context window for sending repository analysis plus recent Docker error output. The app uses model fallback logic so it can continue if the preferred Gemini model is unavailable.

## Docker Usage

Build DockerForge-AI itself:

```bash
docker build -t dockerforge-ai .
```

Run the Streamlit app container with your Gemini credentials:

```bash
docker run --rm -p 8501:8501 --env-file .env -v /var/run/docker.sock:/var/run/docker.sock dockerforge-ai
```

Open `http://localhost:8501`.

The Docker socket mount lets DockerForge-AI call Docker from inside the Streamlit container when it validates generated Dockerfiles. On Windows with Docker Desktop, running the app locally with Python is still the simplest development flow.

## Screenshots

Add screenshots to the `screenshots/` directory after running a demo.

## Known Limitations

- Generated Dockerfiles depend on repository quality and Gemini output.
- Some repositories require secrets, databases, private package registries, or custom runtime configuration.
- Repositories with databases may need runtime variables such as `MONGODB_URI`, `DATABASE_URL`, or `JWT_SECRET`. When the target service runs on the host machine from inside Docker Desktop, `host.docker.internal` may be required instead of `localhost`.
- Container startup verification checks whether the container stays alive briefly; it does not perform deep HTTP health checks for every possible framework.
- Docker-in-Docker style execution requires access to the Docker daemon.
- Private GitHub repositories are not supported by the current clone flow.
- Projects that require paid APIs, cloud credentials, custom native system packages, or multi-service orchestration may still need manual Dockerfile edits.
- The retry loop is limited to a small number of attempts to avoid infinite build/regeneration cycles.

## Future Improvements

- Add HTTP health-check probing for detected ports.
- Add language-specific analyzers for Go, Ruby, PHP, and .NET.
- Add image cleanup and container lifecycle controls in the UI.
- Store run history and generated Dockerfile versions.
- Add support for custom build arguments and environment variables.

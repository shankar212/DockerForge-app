# DockerForge-AI

DockerForge-AI is an AI-powered Dockerfile generator. It accepts a public GitHub repository URL, clones and analyzes the project, asks Gemini to generate a Dockerfile, validates the Dockerfile with `docker build`, retries with build logs when the build fails, and then starts the generated container.

## Architecture

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
- Container startup verification checks whether the container stays alive briefly; it does not perform deep health checks.
- Docker-in-Docker style execution requires access to the Docker daemon.

## Future Improvements

- Add HTTP health-check probing for detected ports.
- Add language-specific analyzers for Go, Ruby, PHP, and .NET.
- Add image cleanup and container lifecycle controls in the UI.
- Store run history and generated Dockerfile versions.
- Add support for custom build arguments and environment variables.

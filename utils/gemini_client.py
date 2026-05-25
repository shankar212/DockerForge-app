from __future__ import annotations

import os
from collections.abc import Iterable

import google.generativeai as genai
from dotenv import load_dotenv


DEFAULT_MODEL_CANDIDATES = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-001",
)


def configure_gemini() -> None:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to .env before using Gemini.")
    genai.configure(api_key=api_key)


def _configured_candidates() -> list[str]:
    configured_model = os.getenv("GEMINI_MODEL", "").strip()
    candidates = [configured_model] if configured_model else []
    candidates.extend(DEFAULT_MODEL_CANDIDATES)
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _list_generate_content_models() -> Iterable[str]:
    try:
        for available_model in genai.list_models():
            methods = getattr(available_model, "supported_generation_methods", []) or []
            name = getattr(available_model, "name", "")
            if "generateContent" in methods and name:
                yield name.replace("models/", "")
    except Exception:
        return


def generate_content_with_fallback(prompt: str) -> tuple[str, str]:
    """Generate text, retrying with available Gemini models when one is unavailable."""
    configure_gemini()
    candidates = _configured_candidates()
    candidates.extend(model for model in _list_generate_content_models() if model not in candidates)

    errors: list[str] = []
    for model_name in candidates:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text or "", model_name
        except Exception as exc:
            message = str(exc)
            errors.append(f"{model_name}: {message}")
            if "not found" not in message.lower() and "not supported" not in message.lower():
                raise RuntimeError(f"Gemini generation failed using {model_name}: {message}") from exc

    detail = "\n".join(errors[-5:])
    raise RuntimeError(f"No Gemini model supporting generateContent was available.\n{detail}")

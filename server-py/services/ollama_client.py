"""
Shared Ollama JSON-mode client.

Used by the admin AI assistant (permission proposals) and the SOP finder.
Both care about the same things:
  - POST /api/chat with format="json", stream=False, temperature=0.1
  - Friendly errors when the model isn't pulled or the daemon is down
  - JSON-decoded response body
"""

from __future__ import annotations

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaError(RuntimeError):
    """Wraps Ollama failures (model missing, daemon down, non-JSON output)
    with a user-facing message. Callers show this in their UI verbatim."""


def call_ollama_json(
    system: str,
    user: str,
    model: str,
    *,
    timeout_s: float = 120.0,
    temperature: float = 0.1,
    base_url: str | None = None,
) -> dict:
    """Single-shot chat call with format="json" enforcement.

    Raises OllamaError on any failure (model missing, network, invalid JSON).
    """
    endpoint = f"{base_url or OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "format": "json",
        "stream": False,
        "options": {"temperature": temperature},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(endpoint, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", "")
        except Exception:
            detail = e.response.text[:200]
        raise OllamaError(
            f"Ollama returned {e.response.status_code}: {detail}. "
            f"Is model '{model}' pulled? Run: ollama pull {model}"
        )
    except httpx.RequestError as e:
        raise OllamaError(
            f"Cannot reach Ollama at {endpoint}: {e}. Is Ollama running? (ollama serve)"
        )

    content = (data.get("message") or {}).get("content", "")
    if not content:
        raise OllamaError("Empty response from Ollama")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("Ollama returned non-JSON (model=%s): %s", model, content[:400])
        raise OllamaError(f"Model returned invalid JSON: {e}")

"""LLM provider seam.

`call_llm` is the single entry point for any AI call in the app. The selection
is env-driven via `PROVIDER_LLM` in config (`mock` | `gcc_copilot`). The mock
implementation routes through Ollama (shared `services/ollama_client.py`); the
real implementation hits the agency's GCC Copilot endpoint.

Every call returns an LLMResponse carrying the exact model identifier — that
identifier is what gets persisted onto the Message and quoted on the §13663
disclosure footer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMResponse:
    content: str
    provider: str                    # "ollama" | "gcc_copilot" | …
    model: str                       # exact model id (goes on the report)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    extra: dict = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    def chat(self, system: str, user: str, *, context: dict | None = None) -> LLMResponse: ...


# ── Mock provider: routes to local Ollama ──────────────────────────────────

class OllamaLLMProvider:
    """Local Ollama provider for dev. Produces well-formed prose responses.

    Uses the chat API directly (not the JSON-mode helper) since cold case
    responses are free text, not JSON."""

    name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or os.environ.get(
            "COLDCASE_LLM_MODEL", "qwen3.6:35b-a3b-nvfp4"
        )
        self.base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )

    def chat(self, system: str, user: str, *, context: dict | None = None) -> LLMResponse:
        import httpx
        endpoint = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0.2},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(timeout=180.0) as client:
                r = client.post(endpoint, json=payload)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError as e:
            # Degrade gracefully so devs without Ollama running can still exercise the flow.
            return LLMResponse(
                content=(
                    f"[mock-llm: Ollama unreachable at {endpoint} — {e}. "
                    f"Echoing the prompt for development.]\n\n"
                    f"PROMPT: {user[:500]}"
                ),
                provider=self.name,
                model=self.model + " (offline-echo)",
            )
        content = (data.get("message") or {}).get("content", "") or "[empty response]"
        return LLMResponse(
            content=content,
            provider=self.name,
            model=self.model,
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=int(data.get("eval_count") or 0),
            extra={"done_reason": data.get("done_reason", "")},
        )


# ── OpenAI provider ────────────────────────────────────────────────────────

class OpenAILLMProvider:
    """OpenAI Chat Completions provider.

    Reads `OPENAI_API_KEY` from env. Model is configurable via
    `OPENAI_MODEL` (default: gpt-4o-mini for cheap dev, easily swapped).

    §13663(a)(1) note: the exact model string returned by OpenAI (e.g.
    "gpt-4o-mini-2024-07-18") is captured onto the Message and surfaces
    on the signed-report disclosure footer.
    """

    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        # Alias (no date suffix) tracks the latest snapshot; the snapshot id
        # OpenAI returns is what lands on the §13663(a)(1) disclosure footer.
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5.5")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def chat(self, system: str, user: str, *, context: dict | None = None) -> LLMResponse:
        if not self.api_key:
            return LLMResponse(
                content="[openai-llm: OPENAI_API_KEY not set — echoing prompt for dev.]\n\n"
                        f"PROMPT: {user[:500]}",
                provider=self.name,
                model=self.model + " (no-key-echo)",
            )
        import httpx
        # Omit `temperature` entirely — newer models (gpt-5.x family) reject
        # any non-default value and we don't want creative variation for
        # cold-case work in the first place. The model's own default is fine.
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=180.0) as client:
                r = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("error", {}).get("message", "")
            except Exception:
                detail = e.response.text[:300]
            return LLMResponse(
                content=f"[openai-llm: HTTP {e.response.status_code} — {detail}]",
                provider=self.name,
                model=self.model + " (http-error)",
            )
        except httpx.HTTPError as e:
            return LLMResponse(
                content=f"[openai-llm: network error — {e}]",
                provider=self.name,
                model=self.model + " (network-error)",
            )
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "") or "[empty response]"
        # Capture the *actual* model identifier the API responded with — this is what
        # ends up on the §13663 disclosure footer.
        actual_model = data.get("model") or self.model
        usage = data.get("usage") or {}
        return LLMResponse(
            content=content,
            provider=self.name,
            model=actual_model,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            extra={
                "openai_response_id": data.get("id", ""),
                "finish_reason": choice.get("finish_reason", ""),
            },
        )


# ── Real provider stub: GCC Copilot ────────────────────────────────────────

class GccCopilotLLMProvider:
    """Microsoft 365 Copilot (GCC) endpoint.

    Real implementation requires the agency's Entra app registration and a
    delegated or service-principal token. Stubbed here so the seam compiles
    and downstream code can be exercised against the mock until the agency
    provides credentials.
    """

    name = "gcc_copilot"

    def __init__(self, *, endpoint: str | None = None, model_hint: str | None = None):
        self.endpoint = endpoint or os.environ.get("GCC_COPILOT_ENDPOINT", "")
        self.model = model_hint or os.environ.get("GCC_COPILOT_MODEL", "gpt-4o-2024-08-06")

    def chat(self, system: str, user: str, *, context: dict | None = None) -> LLMResponse:
        # Intentional NotImplementedError. Wire up when the agency supplies
        # the Entra app credentials and chosen Copilot API surface (Graph
        # /copilot vs. Azure OpenAI deployment in the GCC tenant).
        raise NotImplementedError(
            "GccCopilotLLMProvider is not yet wired. "
            "Set PROVIDER_LLM=mock for development."
        )


# ── Selector ───────────────────────────────────────────────────────────────

def get_llm_provider() -> LLMProvider:
    choice = os.environ.get("PROVIDER_LLM", "mock").lower()
    if choice in ("mock", "ollama"):
        return OllamaLLMProvider()
    if choice in ("openai", "oai"):
        return OpenAILLMProvider()
    if choice in ("gcc", "gcc_copilot", "copilot"):
        return GccCopilotLLMProvider()
    raise ValueError(f"Unknown PROVIDER_LLM={choice!r}")

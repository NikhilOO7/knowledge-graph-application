"""LLM access.

Two layers:
  * ``chat`` / ``chat_json`` — direct calls used by the lightweight agents
    (ontology, context-router, graph-QA) and as a fallback for extraction.
  * ``get_crew_llm`` — returns a CrewAI-compatible LLM object so the extraction
    crew runs on the same provider/model.

Provider is selected via ``LLM_PROVIDER`` (openai | ollama). Both expose an
OpenAI-compatible Chat Completions API, so a single client works for each.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from openai import OpenAI

from ..config import settings

_client: Optional[OpenAI] = None


def _openai_client() -> OpenAI:
    global _client
    if _client is None:
        if settings.llm_provider == "ollama":
            _client = OpenAI(
                base_url=f"{settings.ollama_base_url}/v1",
                api_key="ollama",  # ollama ignores the key
            )
        else:
            _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def model_name() -> str:
    return settings.ollama_model if settings.llm_provider == "ollama" else settings.openai_model


def chat(system: str, user: str, temperature: float = 0.3) -> str:
    """Plain text completion."""
    resp = _openai_client().chat.completions.create(
        model=model_name(),
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def chat_json(
    system: str, user: str, temperature: float = 0.2, retries: int = 2
) -> Dict[str, Any]:
    """JSON-mode completion with retry + tolerant parsing."""
    system_json = system + "\n\nRespond with ONLY a valid JSON object, no markdown."
    last_err: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            kwargs: Dict[str, Any] = dict(
                model=model_name(),
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_json},
                    {"role": "user", "content": user},
                ],
            )
            # Native JSON mode where supported.
            try:
                kwargs["response_format"] = {"type": "json_object"}
                resp = _openai_client().chat.completions.create(**kwargs)
            except Exception:
                kwargs.pop("response_format", None)
                resp = _openai_client().chat.completions.create(**kwargs)
            return _parse_json(resp.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    raise RuntimeError(f"LLM JSON parse failed after {retries + 1} attempts: {last_err}")


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def get_crew_llm():
    """Return a CrewAI LLM bound to the configured provider, or None.

    CrewAI uses LiteLLM under the hood; provider prefixes select the backend.
    """
    try:
        from crewai import LLM
    except Exception:
        return None

    if settings.llm_provider == "ollama":
        return LLM(
            model=f"ollama/{settings.ollama_model}",
            base_url=settings.ollama_base_url,
        )
    return LLM(
        model=f"openai/{settings.openai_model}",
        api_key=settings.openai_api_key,
    )

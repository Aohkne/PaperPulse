"""Multi-provider LLM caller — routes to the correct SDK based on PROVIDER env."""

import logging

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _make_openai_client(base_url: str | None = None):
    from openai import AsyncOpenAI

    settings = get_settings()
    return AsyncOpenAI(api_key=settings.llm_api_key, base_url=base_url or None)


def _make_anthropic_client():
    from anthropic import AsyncAnthropic

    settings = get_settings()
    return AsyncAnthropic(api_key=settings.llm_api_key)


async def chat_completion(
    messages: list[dict[str, str]],
    temperature: float | None = None,
    **kwargs,
) -> str:
    """Send a chat completion request to the configured LLM provider.

    temperature: per-call override; falls back to settings.llm_temperature.
    """
    settings = get_settings()
    provider = settings.provider
    effective_temp = temperature if temperature is not None else settings.llm_temperature

    if provider in ("openai", "custom"):
        client = _make_openai_client(base_url=settings.llm_base_url or None)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=effective_temp,
            **kwargs,
        )
        choices = response.choices
        if not choices:
            logger.warning("llm_client: response.choices is None/empty — returning empty string")
            return ""
        return choices[0].message.content or ""

    if provider == "anthropic":
        client = _make_anthropic_client()
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_msgs = [m for m in messages if m["role"] != "system"]
        response = await client.messages.create(
            model=settings.llm_model,
            system=system,
            messages=user_msgs,
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return response.content[0].text

    raise ValueError(f"Unsupported provider: {provider}")

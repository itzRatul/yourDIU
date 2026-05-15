"""
Groq Service
============
LLaMA 3.3 70B via Groq API.
- Round-robin key rotation across up to 3 API keys
- Streaming support (SSE)
- Non-streaming for internal use
"""

import logging
import itertools
from typing import AsyncIterator, Optional

from groq import AsyncGroq, APIStatusError

from app.core.config import settings

logger = logging.getLogger("yourDIU.groq")

# ── Round-robin key iterator ─────────────────────────────────────────────────

def _make_key_cycle():
    keys = settings.groq_api_keys
    if not keys:
        raise RuntimeError("No Groq API keys configured.")
    return itertools.cycle(keys)

_key_cycle = None

def _next_key() -> str:
    global _key_cycle
    if _key_cycle is None:
        _key_cycle = _make_key_cycle()
    return next(_key_cycle)


# ── System prompt ────────────────────────────────────────────────────────────

DIU_SYSTEM_PROMPT = """You are yourDIU Assistant — a helpful AI for Daffodil International University (DIU), Bangladesh.

You help students and teachers with:
- Class routines, teacher schedules, and availability
- University rules, notices, and academic information
- General academic questions

Guidelines:
- Answer in the same language the user writes in (Bangla or English)
- Be concise and accurate
- If you don't know something, say so honestly
- For routine/schedule queries, use the provided context
- For DIU-specific info, prefer the retrieved knowledge base context over general knowledge
- Never make up teacher schedules or official information
"""


# ── Chat completion ──────────────────────────────────────────────────────────

async def chat_completion(
    messages: list[dict],
    system_prompt: str = DIU_SYSTEM_PROMPT,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Non-streaming completion. Returns full response string."""
    api_key = _next_key()
    client = AsyncGroq(api_key=api_key)

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except APIStatusError as e:
        logger.error("Groq API error: %s", e)
        raise


async def chat_completion_stream(
    messages: list[dict],
    system_prompt: str = DIU_SYSTEM_PROMPT,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    """Streaming completion. Yields text chunks as they arrive."""
    api_key = _next_key()
    client = AsyncGroq(api_key=api_key)

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        stream = await client.chat.completions.create(
            model=settings.groq_model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except APIStatusError as e:
        logger.error("Groq stream error: %s", e)
        raise


async def quick_classify(text: str, options: list[str]) -> str:
    """
    Lightweight classification call.
    Returns one of the options or 'unknown'.
    Used by brain_service to route queries.
    """
    options_str = " | ".join(options)
    prompt = f"Classify this query into exactly one category: {options_str}\n\nQuery: {text}\n\nReply with only the category name."
    try:
        result = await chat_completion(
            [{"role": "user", "content": prompt}],
            system_prompt="You are a query classifier. Reply with only the category name, nothing else.",
            temperature=0.0,
            max_tokens=20,
        )
        result = result.strip().lower()
        for opt in options:
            if opt.lower() in result:
                return opt
        return "unknown"
    except Exception:
        return "unknown"

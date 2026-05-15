"""
Gemini Service
==============
Google Gemini 2.0 Flash via google-generativeai SDK.
Used as:
  - Fallback when Groq fails / rate-limited
  - PDF Vision parsing (routine PDF fallback)
  - Multimodal tasks
"""

import logging
from typing import Optional

import google.generativeai as genai

from app.core.config import settings

logger = logging.getLogger("yourDIU.gemini")

_configured = False

def _ensure_configured():
    global _configured
    if not _configured:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not set.")
        genai.configure(api_key=settings.gemini_api_key)
        _configured = True


def _get_model(model_name: Optional[str] = None) -> genai.GenerativeModel:
    _ensure_configured()
    return genai.GenerativeModel(model_name or settings.gemini_model)


# ── Text completion ──────────────────────────────────────────────────────────

async def chat_completion(
    messages: list[dict],
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """
    Non-streaming Gemini completion.
    Converts OpenAI-style messages to Gemini format.
    """
    _ensure_configured()
    model = _get_model()

    # Convert messages to Gemini format
    gemini_history = []
    user_message = ""

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            gemini_history.append({"role": "user", "parts": [content]})
            user_message = content
        elif role == "assistant":
            gemini_history.append({"role": "model", "parts": [content]})

    # Prepend system prompt to first user message if provided
    if system_prompt and gemini_history:
        first_user = gemini_history[0]
        if first_user["role"] == "user":
            first_user["parts"] = [f"{system_prompt}\n\n{first_user['parts'][0]}"]

    try:
        chat = model.start_chat(history=gemini_history[:-1] if len(gemini_history) > 1 else [])
        response = await chat.send_message_async(
            user_message,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text or ""
    except Exception as e:
        logger.error("Gemini API error: %s", e)
        raise


async def analyze_image_bytes(
    image_bytes: bytes,
    prompt: str,
    mime_type: str = "application/pdf",
) -> str:
    """
    Send raw bytes (PDF page image) to Gemini Vision.
    Used as fallback when pdfplumber fails to parse a routine page.
    """
    _ensure_configured()
    model = _get_model("gemini-2.0-flash")

    part = {"mime_type": mime_type, "data": image_bytes}
    try:
        response = await model.generate_content_async([part, prompt])
        return response.text or ""
    except Exception as e:
        logger.error("Gemini Vision error: %s", e)
        raise

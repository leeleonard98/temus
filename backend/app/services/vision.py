"""Vision service — describe one or many images via the OpenAI Chat API.

Encodes images as base64 data URLs and sends them as `image_url` content
parts. Falls back to a stub when no API key is configured so tests and
offline dev paths still work.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import settings

DEFAULT_PROMPT = "Describe this image for a wealth manager."


def _data_url(path: str | Path) -> str:
    """Read `path` and return a base64 data URL (`data:<mime>;base64,...`)."""
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    payload = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


async def describe_image(path: str | Path, prompt: str = DEFAULT_PROMPT) -> str:
    """Single-image description (V4)."""
    return await describe_images([path], prompt=prompt)


async def describe_images(
    paths: list[str | Path], prompt: str = DEFAULT_PROMPT
) -> str:
    """Multi-image description in one prompt (V2).

    All images go in a single user turn so the model can compare/cross-reference.
    """
    if not paths:
        return ""

    if not settings.openai_api_key:
        joined = ", ".join(str(p) for p in paths)
        return f"[stub] would describe {len(paths)} image(s): {joined}"

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    parts: list[dict] = [{"type": "text", "text": prompt}]
    for p in paths:
        parts.append({"type": "image_url", "image_url": {"url": _data_url(p)}})

    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": parts}],
        max_tokens=600,
    )
    return resp.choices[0].message.content or ""

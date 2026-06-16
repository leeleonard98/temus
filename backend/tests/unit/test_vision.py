"""Unit tests for the vision service stub fallback (V1, V2, V4)."""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_describe_image_uses_stub_when_no_api_key(tmp_path) -> None:
    """No key → returns a stub string mentioning the path; no API call."""
    from app.services import vision

    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    with patch.object(vision.settings, "openai_api_key", ""):
        out = await vision.describe_image(img)

    assert "[stub]" in out
    assert "x.png" in out


@pytest.mark.asyncio
async def test_describe_images_handles_empty_list() -> None:
    """No images → empty string, no crash."""
    from app.services import vision

    assert await vision.describe_images([]) == ""


def test_data_url_encodes_path_with_correct_mime(tmp_path) -> None:
    """`_data_url` chooses the mime from extension and base64-encodes the bytes."""
    from app.services import vision

    p = tmp_path / "snip.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nbody")
    url = vision._data_url(p)
    assert url.startswith("data:image/png;base64,")

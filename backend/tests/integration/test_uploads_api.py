"""Integration tests for upload + describe endpoints (V1, V2, V4)."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# Minimal valid 1x1 PNG (the PNG magic + chunks). Good enough for upload tests.
_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63f8cf00000003000100182ddd8a0000000049454e44ae426082"
)


async def test_upload_image_accepts_png(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/uploads/image",
        files={"file": ("tiny.png", io.BytesIO(_PNG_1X1), "image/png")},
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["mime"] == "image/png"
    assert body["bytes"] == len(_PNG_1X1)
    assert body["id"]
    assert body["path"].endswith(".png")
    # File should actually exist on disk.
    p = Path(__file__).resolve().parents[3] / body["path"]
    assert p.exists()


async def test_upload_image_rejects_text_with_friendly_workaround(
    client: AsyncClient,
) -> None:
    res = await client.post(
        "/api/v1/uploads/image",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert res.status_code == 415
    detail = res.json()["detail"]
    assert detail["error"] == "unsupported file type"
    assert "image/png" in detail["supported"]
    assert "workaround" in detail and detail["workaround"]


async def test_upload_image_rejects_oversized(client: AsyncClient) -> None:
    """Anything over MAX_BYTES is rejected with 413 — we patch the cap so the
    test stays small (no need to send a real 25 MB body)."""
    from app.routers import uploads

    original = uploads.MAX_BYTES
    uploads.MAX_BYTES = 16  # tiny cap
    try:
        res = await client.post(
            "/api/v1/uploads/image",
            files={"file": ("big.png", io.BytesIO(_PNG_1X1), "image/png")},
        )
        assert res.status_code == 413
        assert res.json()["detail"]["error"] == "file too large"
    finally:
        uploads.MAX_BYTES = original


async def test_describe_returns_stub_text_when_no_api_key(client: AsyncClient) -> None:
    """Upload then describe — stub vision returns a placeholder including the path."""
    from app.services import vision

    # Force stub regardless of .env.
    original_key = vision.settings.openai_api_key
    vision.settings.openai_api_key = ""
    try:
        upload = await client.post(
            "/api/v1/uploads/image",
            files={"file": ("x.png", io.BytesIO(_PNG_1X1), "image/png")},
        )
        assert upload.status_code == 201, upload.text
        image_id = upload.json()["id"]

        res = await client.post(
            "/api/v1/uploads/describe",
            json={"image_ids": [image_id], "question": "what is this?"},
        )
    finally:
        vision.settings.openai_api_key = original_key

    assert res.status_code == 200
    body = res.json()
    assert "[stub]" in body["description"]
    assert body["image_ids"] == [image_id]


async def test_describe_404s_for_unknown_image_id(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/uploads/describe",
        json={"image_ids": ["does-not-exist"], "question": "q"},
    )
    assert res.status_code == 404

"""Image upload + describe endpoints (V1, V2, V4)."""
from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.services import vision

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Public assets dir for uploaded files. Lives outside backend/ so multiple
# processes (uvicorn reloads, scripts, tests) all see the same files.
UPLOAD_DIR = Path(__file__).resolve().parents[3] / "assets" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB

EXT_FOR_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class UploadOut(BaseModel):
    id: str
    path: str
    mime: str
    bytes: int


class DescribeIn(BaseModel):
    image_ids: list[str] = Field(..., min_length=1, max_length=10)
    question: str = Field("Describe these images for a wealth manager.", max_length=2000)


class DescribeOut(BaseModel):
    description: str
    image_ids: list[str]


def _resolve_image(image_id: str) -> Path:
    """Find the on-disk file for a stored image id (uuid stem)."""
    for ext in EXT_FOR_MIME.values():
        p = UPLOAD_DIR / f"{image_id}{ext}"
        if p.exists():
            return p
    raise HTTPException(status_code=404, detail=f"image {image_id} not found")


@router.post(
    "/image",
    response_model=UploadOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_image(file: UploadFile = File(...)) -> UploadOut:
    """Accept JPEG/PNG/WebP. Reject other types with a friendly hint (V4)."""
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    if mime not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": "unsupported file type",
                "received": mime or "unknown",
                "supported": sorted(ALLOWED_MIMES),
                "workaround": (
                    "Convert to PNG/JPG with `sips`, Preview, or your image "
                    "viewer and re-upload."
                ),
            },
        )

    # Stream to disk so we don't load big files entirely in memory.
    image_id = uuid.uuid4().hex
    ext = EXT_FOR_MIME[mime]
    out_path = UPLOAD_DIR / f"{image_id}{ext}"
    total = 0
    with out_path.open("wb") as f:
        while chunk := await file.read(64 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                f.close()
                out_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail={
                        "error": "file too large",
                        "max_bytes": MAX_BYTES,
                    },
                )
            f.write(chunk)

    return UploadOut(
        id=image_id,
        path=str(out_path.relative_to(UPLOAD_DIR.parent.parent)),
        mime=mime,
        bytes=total,
    )


@router.post("/describe", response_model=DescribeOut)
async def describe(body: DescribeIn) -> DescribeOut:
    """Run vision (V2) over one-or-many uploaded images and return the answer."""
    paths = [_resolve_image(i) for i in body.image_ids]
    answer = await vision.describe_images([str(p) for p in paths], prompt=body.question)
    return DescribeOut(description=answer, image_ids=body.image_ids)

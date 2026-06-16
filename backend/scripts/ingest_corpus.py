"""Ingest the markdown corpus under assets/corpus/ into documents + chunks.

Usage:
    python -m scripts.ingest_corpus               # incremental (truncate-then-insert)
    python -m scripts.ingest_corpus --clean       # explicit truncate

Idempotent on filename: every run wipes the documents and chunks tables and
re-ingests from disk, so the script is safe to re-run after editing corpus
files. (We re-run rarely; this beats a per-file diff.)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

from sqlalchemy import delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Allow running this both as `python -m scripts.ingest_corpus` and `python ingest_corpus.py`.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import settings  # noqa: E402
from app.db.models import Chunk, Document  # noqa: E402
from app.services.embeddings import embed  # noqa: E402

CORPUS_DIR = _BACKEND.parent / "assets" / "corpus"

# Chunking — character-based to avoid a tiktoken dep. ~600 chars ≈ 150 tokens
# of typical English prose; 100 char overlap preserves context across boundaries.
CHUNK_TARGET_CHARS = 600
CHUNK_OVERLAP_CHARS = 100

# Map filename prefix → language tag. Anything else defaults to "en".
LANG_PREFIXES = {"zh": "zh", "de": "de", "fr": "fr", "es": "es"}


def chunk_text(s: str, *, size: int = CHUNK_TARGET_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split text into ~`size`-char chunks with `overlap` chars of carry-over.

    Tries to break at paragraph or sentence boundaries when one falls inside
    the last 20% of the window — keeps chunks self-contained.
    """
    s = s.strip()
    if len(s) <= size:
        return [s] if s else []
    chunks: list[str] = []
    start = 0
    while start < len(s):
        end = min(start + size, len(s))
        if end < len(s):
            window_start = max(start + int(size * 0.8), start + 1)
            search = s[window_start:end]
            for sep in ("\n\n", "\n", ". ", "; ", ", "):
                idx = search.rfind(sep)
                if idx != -1:
                    end = window_start + idx + len(sep)
                    break
        chunk = s[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(s):
            break
        start = max(end - overlap, start + 1)
    return chunks


def detect_lang(filename: str) -> str:
    """zh_*, de_*, etc. → language tag; otherwise 'en'."""
    m = re.match(r"^\d+_([a-z]{2})_", filename)
    if m and m.group(1) in LANG_PREFIXES:
        return LANG_PREFIXES[m.group(1)]
    return "en"


def title_from(path: Path, body: str) -> str:
    """Use the first H1 as the title, else humanise the filename stem."""
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").lstrip("0123456789 ").title()


async def ingest(clean: bool = False) -> tuple[int, int]:
    """Ingest the whole corpus directory. Returns (n_docs, n_chunks)."""
    files = sorted(CORPUS_DIR.glob("*.md"))
    if not files:
        print(f"No corpus files found under {CORPUS_DIR}")
        return (0, 0)

    # Build sync URL for the script — settings.database_url is the asyncpg one.
    engine = create_async_engine(settings.database_url, future=True)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    n_docs = 0
    n_chunks = 0
    async with Session() as session:
        # Truncate tables either explicitly (--clean) or implicitly so re-running
        # the script gives a known-good state.
        if clean or True:
            await session.execute(delete(Chunk))
            await session.execute(delete(Document))
            await session.commit()

        for path in files:
            body = path.read_text(encoding="utf-8")
            doc = Document(
                source_uri=str(path.relative_to(CORPUS_DIR.parent)),
                title=title_from(path, body),
                lang=detect_lang(path.name),
                doc_type="markdown",
                metadata_json={"filename": path.name},
            )
            session.add(doc)
            await session.flush()  # populate doc.id

            chunks = chunk_text(body)
            if not chunks:
                continue
            embeddings = await embed(chunks)
            for ord_, (content, vec) in enumerate(zip(chunks, embeddings, strict=True)):
                session.add(
                    Chunk(
                        document_id=doc.id,
                        ord=ord_,
                        content=content,
                        token_count=len(content) // 4,  # rough char→token estimate
                        embedding=vec,
                        # to_tsvector is set after flush via UPDATE — easier than
                        # threading server-side defaults through the ORM mapping.
                    )
                )
            await session.flush()
            n_docs += 1
            n_chunks += len(chunks)
            print(f"  ingested {path.name}: {len(chunks)} chunks (lang={doc.lang})")

        # Populate content_tsv server-side for every chunk in one shot.
        # Use 'simple' for non-English where the english stemmer would do more
        # harm than good. simple = normalise case, no stemming.
        await session.execute(
            text(
                """
                UPDATE chunks
                SET content_tsv = to_tsvector(
                    (CASE WHEN d.lang = 'en' THEN 'english' ELSE 'simple' END)::regconfig,
                    chunks.content
                )
                FROM documents d
                WHERE chunks.document_id = d.id
                """
            )
        )
        await session.commit()

    await engine.dispose()
    return (n_docs, n_chunks)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--clean", action="store_true", help="(no-op — every run truncates)")
    args = p.parse_args()
    n_docs, n_chunks = asyncio.run(ingest(clean=args.clean))
    print(f"\ningested {n_docs} document(s), {n_chunks} chunk(s)")


if __name__ == "__main__":
    main()

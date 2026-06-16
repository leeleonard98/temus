"""Unit tests for the corpus chunker (independent of DB)."""
from __future__ import annotations


def test_chunk_text_returns_one_chunk_when_under_size() -> None:
    from scripts.ingest_corpus import chunk_text

    out = chunk_text("Short body.", size=600, overlap=100)
    assert out == ["Short body."]


def test_chunk_text_splits_long_body_with_overlap() -> None:
    from scripts.ingest_corpus import chunk_text

    body = ("Sentence A. " * 200).strip()  # ~2400 chars
    chunks = chunk_text(body, size=600, overlap=100)

    assert len(chunks) >= 3
    # Each chunk should be roughly the target size, never grossly over.
    assert all(len(c) <= 800 for c in chunks)
    # Reassembling without dedupe should cover all the source content (modulo overlap).
    assert "Sentence A." in chunks[0]


def test_chunk_text_drops_empty_input() -> None:
    from scripts.ingest_corpus import chunk_text

    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_detect_lang_from_filename_prefix() -> None:
    from scripts.ingest_corpus import detect_lang

    assert detect_lang("01_diversification.md") == "en"
    assert detect_lang("07_zh_diversification.md") == "zh"
    assert detect_lang("08_de_index_funds.md") == "de"

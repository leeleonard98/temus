"""Subprocess smoke test for the REPL chat client.

Spawns `python -m scripts.repl_chat ... --role client`, pipes a single
message + `/exit`, asserts clean exit and that the stub LLM output appears.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("role", ["client", "advisor"])
def test_repl_smoke_streams_stub_and_exits_clean(role: str) -> None:
    repo_backend = Path(__file__).resolve().parents[2]  # backend/
    env = os.environ.copy()
    # Force offline stub.
    env["OPENAI_API_KEY"] = ""
    # Use the dev DB (must be migrated to head — caller's responsibility).
    # The REPL writes a real row; that's fine, it's idempotent by email.

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.repl_chat",
            "--email",
            f"smoke-{role}@aura.test",
            "--role",
            role,
            "--name",
            f"smoke-{role}",
        ],
        cwd=repo_backend,
        env=env,
        input="hello there\n/exit\n",
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, (
        f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
    )
    # Stub yields '[stub] echo: hello there'.
    assert "[stub]" in proc.stdout
    assert "hello there" in proc.stdout
    # Banner must surface the role so users see who they are.
    assert role in proc.stdout.lower()

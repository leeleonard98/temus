"""Langfuse tracing — opt-in.

If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set the module returns a
real Langfuse client and a `@traced(name)` decorator that wraps async functions
in an observation. Otherwise both fall back to no-ops so the rest of the app
runs identically without any tracing.
"""
from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.config import settings

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])

_client: Any | None = None
_initialised = False


def get_client() -> Any | None:
    """Return a singleton Langfuse client, or None when tracing is disabled."""
    global _client, _initialised
    if _initialised:
        return _client
    _initialised = True

    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info("Langfuse keys not set; tracing disabled")
        return None

    try:
        from langfuse import Langfuse  # type: ignore
    except Exception as e:  # pragma: no cover -- dep missing
        logger.warning("langfuse import failed (%s); tracing disabled", e)
        return None

    try:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as e:
        logger.warning("Langfuse init failed (%s); tracing disabled", e)
        _client = None
    return _client


def traced(name: str) -> Callable[[_F], _F]:
    """Decorator: wrap an async function in a Langfuse observation.

    Quietly degrades to a passthrough if the client isn't available or the
    SDK shape is different than expected — the underlying function always runs.
    """

    def decorator(fn: _F) -> _F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_client()
            if client is None:
                return await fn(*args, **kwargs)

            ctx_factory = getattr(client, "start_as_current_observation", None)
            if ctx_factory is None:
                # Older / different SDK — best effort: just run the function.
                return await fn(*args, **kwargs)
            try:
                with ctx_factory(name=name, as_type="generation"):
                    return await fn(*args, **kwargs)
            except Exception:
                # Never let tracing failures fail real work.
                return await fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def wrap_stream_chat(stream_fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an async-generator `stream_chat(messages, model=None)` so each
    invocation lands as a Langfuse `generation` observation.

    Captures input messages, model, and the assembled output text. Falls back
    to a no-op identity wrapper when Langfuse isn't configured.
    """
    client = get_client()
    if client is None:
        return stream_fn

    @functools.wraps(stream_fn)
    async def wrapped(messages: list[dict], model: str | None = None, **kwargs: Any):
        ctx_factory = getattr(client, "start_as_current_observation", None)
        if ctx_factory is None:
            async for tok in stream_fn(messages, model=model, **kwargs):
                yield tok
            return

        # Resolve the model name eagerly so the trace records what *will* be used,
        # not just what was passed in.
        from app.core.config import settings as _settings

        observed_model = model or _settings.openai_model

        try:
            with ctx_factory(
                name="stream_chat",
                as_type="generation",
                input=messages,
                model=observed_model,
            ) as obs:
                collected: list[str] = []
                try:
                    async for tok in stream_fn(messages, model=model, **kwargs):
                        collected.append(tok)
                        yield tok
                finally:
                    # Always try to attach the assembled output, even if the
                    # consumer aborted mid-stream. Best-effort: if the SDK
                    # shape doesn't expose .update, swallow.
                    try:
                        if obs is not None and hasattr(obs, "update"):
                            obs.update(output="".join(collected))
                    except Exception:  # pragma: no cover -- defensive
                        logger.debug("langfuse obs.update failed", exc_info=True)
        except Exception:
            # If the observation context itself errors, never fail the caller.
            async for tok in stream_fn(messages, model=model, **kwargs):
                yield tok

    return wrapped

"""Canonical LLM router for RG_System_Agents.

Thin adapter on top of `rg_llm.UnifiedLLMClient` (the single source of
truth for LLM access across the platform — volume-mounted as
/app/rg_llm in every container that needs it).

Exposes only what the migrated agent engines actually use:

    router.route_query(message, context, preferred_provider, images,
                       preferred_model=None, user_keys=None)
        -> {"response": str, "provider": str, "metadata": dict}

    router.set_user_api_keys(keys: dict)

No MultiAIRouter, no provider chains, no chat-side wrapper.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from rg_llm import LLMRequest, UnifiedLLMClient

logger = logging.getLogger(__name__)


def _to_messages(message: str, context: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    msgs: List[Dict[str, Any]] = []
    if context:
        for m in context:
            role = m.get("role", "user")
            content = m.get("content", "")
            if content:
                msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": message})
    return msgs


class CanonicalRouter:
    """Singleton-ish adapter; per-request user keys are stored via
    thread-local so concurrent agent calls don't cross-contaminate."""

    def __init__(self) -> None:
        self._client = UnifiedLLMClient()
        self._tls = threading.local()

    def set_user_api_keys(self, keys: Optional[Dict[str, str]]) -> None:
        clean = {k: v for k, v in (keys or {}).items() if not k.startswith("__")} or None
        self._tls.user_keys = clean

    def _user_keys(self) -> Optional[Dict[str, str]]:
        return getattr(self._tls, "user_keys", None)

    async def route_query(
        self,
        message: str,
        context: Optional[List[Dict[str, Any]]] = None,
        preferred_provider: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        preferred_model: Optional[str] = None,
        user_keys: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        keys = user_keys
        if keys is None:
            keys = self._user_keys()
        clean_keys = {k: v for k, v in (keys or {}).items() if not k.startswith("__")} or None

        messages = _to_messages(message, context)
        # Attach images to the last user message if present
        if images and messages:
            last_msg = messages[-1]
            if last_msg.get("role") == "user":
                content_parts = [{"type": "text", "text": last_msg["content"]}]
                for img in images:
                    url = img.get("url") or img.get("base64_data") or ""
                    if url:
                        content_parts.append({"type": "image_url", "image_url": {"url": url}})
                last_msg["content"] = content_parts

        req = LLMRequest(
            messages=messages,
            provider=preferred_provider,
            model=preferred_model,
        )
        try:
            resp = await self._client.complete(req, user_keys=clean_keys)
        except Exception as e:
            logger.exception("CanonicalRouter.route_query failed")
            return {
                "response": "",
                "provider": "error",
                "metadata": {"error": f"{type(e).__name__}: {e}"},
            }

        return {
            "response": getattr(resp, "content", "") or "",
            "provider": getattr(resp, "provider", "unknown") or "unknown",
            "metadata": {
                "model": getattr(resp, "model", None),
                "fallback_chain": getattr(resp, "fallback_chain", None),
                "was_fallback": getattr(resp, "was_fallback", False),
                "usage": getattr(resp, "usage", None),
            },
        }


_router = CanonicalRouter()


def get_router_for_internal_use() -> CanonicalRouter:
    """Backwards-compatible accessor used by `domain/agent/facade.py`."""
    return _router

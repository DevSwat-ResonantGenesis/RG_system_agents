"""Canonical memory adapter for RG_System_Agents.

`agent_memory_store` is preserved as a name (so `domain/agent/facade.py`
keeps importing it unchanged) but is now a thin synchronous-friendly
HTTP client over RG_Memory — the single source of truth for memory
across the platform.

Endpoints used:
    POST {RG_MEMORY_URL}/memory/ingest    (store)
    POST {RG_MEMORY_URL}/memory/retrieve  (retrieve)
    GET  {RG_MEMORY_URL}/memory/stats     (stats)

Failures are swallowed and logged — agent flow must not crash if
memory is briefly unavailable.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


def _memory_url() -> str:
    return os.getenv("RG_MEMORY_URL", "http://memory_service:8000").rstrip("/")


def _internal_secret() -> Optional[str]:
    return os.getenv("INTERNAL_SECRET")


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    s = _internal_secret()
    if s:
        h["X-Internal-Secret"] = s
    return h


@dataclass
class MemoryRecord:
    """Lightweight record matching the field names the facade reads
    (`task`, `response`)."""
    task: str
    response: str
    metadata: Dict[str, Any]


class _AgentMemoryStore:
    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = timeout

    def store(
        self,
        agent_type: str,
        user_id: str,
        task: str,
        response: str,
        context: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        payload = {
            "user_id": user_id,
            "content": f"AGENT[{agent_type}] TASK: {task}\nRESPONSE: {response}",
            "metadata": {
                "kind": "agent_interaction",
                "agent_type": agent_type,
                "task": task,
                "response": response,
            },
            "generate_embedding": True,
        }
        try:
            with httpx.Client(timeout=self._timeout) as c:
                r = c.post(f"{_memory_url()}/memory/ingest",
                           json=payload, headers=_headers())
                r.raise_for_status()
                return True
        except Exception as e:
            logger.warning(f"agent_memory_store.store failed: {e}")
            return False

    def retrieve(
        self,
        agent_type: str,
        user_id: str,
        query: str,
        limit: int = 3,
    ) -> List[MemoryRecord]:
        payload = {
            "user_id": user_id,
            "query": query,
            "limit": limit,
            "filters": {"kind": "agent_interaction", "agent_type": agent_type},
        }
        try:
            with httpx.Client(timeout=self._timeout) as c:
                r = c.post(f"{_memory_url()}/memory/retrieve",
                           json=payload, headers=_headers())
                r.raise_for_status()
                data = r.json() or []
        except Exception as e:
            logger.warning(f"agent_memory_store.retrieve failed: {e}")
            return []

        out: List[MemoryRecord] = []
        for item in data if isinstance(data, list) else []:
            md = item.get("metadata") or {}
            out.append(MemoryRecord(
                task=md.get("task") or item.get("content", "")[:200],
                response=md.get("response") or "",
                metadata=md,
            ))
        return out

    def get_stats(self) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=self._timeout) as c:
                r = c.get(f"{_memory_url()}/memory/stats", headers=_headers())
                r.raise_for_status()
                return r.json() or {}
        except Exception as e:
            logger.warning(f"agent_memory_store.get_stats failed: {e}")
            return {"unavailable": True, "error": str(e)}


agent_memory_store = _AgentMemoryStore()

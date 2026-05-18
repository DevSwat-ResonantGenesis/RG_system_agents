"""
RG_System_Agents — System-Level Agent Orchestration Service
============================================================

Owns the cognitive layer extracted from RG_Chat:
  - Multi-agent debate / voting / chaining / team composition
  - Autonomous planner & executor
  - Self-improving agent feedback loop
  - Decision framework, task analyzer, capability registry
  - Agent metrics, confidence, specialization
  - Agent classifier (ML routing of user requests to system agents)

Distinct from RG_Agent_Engine (which owns *user-published* agents,
agent wallets, custom tools, scheduling, autonomous daemons).

This service is the brain that makes RG_Chat respond intelligently.
RG_Chat dispatches every cognitive task here over HTTP.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.agent import router as agent_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[RG_System_Agents] starting up")
    # Pre-load classifier (best-effort; non-fatal)
    try:
        from .services.agent_classifier import preload_agent_classifier
        await preload_agent_classifier()
        logger.info("[RG_System_Agents] agent_classifier preloaded")
    except Exception as e:
        logger.warning(f"[RG_System_Agents] classifier preload skipped: {e}")
    yield
    logger.info("[RG_System_Agents] shutting down")


app = FastAPI(
    title="RG_System_Agents",
    description="System-level agent orchestration (debate, voting, chaining, autonomous planner)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "rg_system_agents", "version": "0.1.0"}


@app.get("/")
async def root():
    return {
        "service": "rg_system_agents",
        "endpoints": [
            "/health",
            "/agent/debate",
            "/agent/spawn",
            "/agent/team",
            "/agent/voting",
            "/agent/chain",
            "/agent/confidence",
            "/agent/feedback",
            "/agent/feedback/stats",
            "/agent/stats",
            "/agent/teams",
            "/agent/chains",
            "/agent/validate",
            "/agent/citations",
            "/agent/hallucinations",
            "/agent/project_context",
        ],
    }


app.include_router(agent_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

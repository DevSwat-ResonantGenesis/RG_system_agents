"""HTTP surface for the system-agent facade.

Each route is a 1:1 thin wrapper over a function in
`app.domain.agent.facade`. RG_Chat (and any other internal caller)
invokes these endpoints via httpx; no caller imports the facade
module directly.

NOTE: the cognitive helpers and engines were ported verbatim from
RG_Chat in this initial extraction. Some of them still depend on
modules that have not been migrated yet (e.g. memory). Routes that
hit those code paths will surface their underlying exception as
HTTP 500 until the follow-up "deback fix wier" pass.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ---- Pydantic request models -------------------------------------------------

class DebateRequest(BaseModel):
    message: str
    context_messages: List[Dict[str, Any]] = Field(default_factory=list)
    preferred_provider: Optional[str] = None
    images: Optional[List[Dict[str, Any]]] = None


class SpawnRequest(BaseModel):
    message: str
    context_messages: List[Dict[str, Any]] = Field(default_factory=list)
    user_id: Optional[str] = None
    user_api_keys: Optional[Dict[str, str]] = None
    preferred_provider: Optional[str] = None
    forced_agent_type: Optional[str] = None
    images: Optional[List[Dict[str, Any]]] = None


class TeamRequest(BaseModel):
    message: str
    context_messages: List[Dict[str, Any]] = Field(default_factory=list)
    team_id: Optional[str] = None
    user_id: Optional[str] = None
    preferred_provider: Optional[str] = None


class VotingRequest(BaseModel):
    task: str
    context: List[Dict[str, Any]] = Field(default_factory=list)
    agent_types: Optional[List[str]] = None
    preferred_provider: Optional[str] = None


class ConfidenceRequest(BaseModel):
    response: str
    task: str = ""


class FeedbackRequest(BaseModel):
    user_id: str
    agent_type: str
    rating: int
    task: str = ""
    response: str = ""
    feedback_text: str = ""


class ChainRunRequest(BaseModel):
    chain_id: str
    initial_input: str
    user_id: Optional[str] = None
    preferred_provider: Optional[str] = None


class ChainCreateRequest(BaseModel):
    user_id: str
    name: str
    steps: List[Dict[str, Any]]
    description: str = ""


class ValidateRequest(BaseModel):
    task: str
    response: str
    context: Optional[List[Dict[str, Any]]] = None
    preferred_provider: Optional[str] = None


class CitationsRequest(BaseModel):
    response: str
    task: str = ""
    agent_type: str = ""


class HallucinationRequest(BaseModel):
    response: str
    task: str = ""


class ProjectContextRead(BaseModel):
    user_id: str
    project_name: str


class ProjectContextWrite(BaseModel):
    user_id: str
    project_name: str
    context: Dict[str, Any]


# ---- helper ------------------------------------------------------------------

def _facade():
    # Lazy import — avoids paying engine init cost at module load
    from ..domain.agent import facade
    return facade


def _wrap(call):
    try:
        return call()
    except Exception as e:
        logger.exception("facade call failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


# ---- routes ------------------------------------------------------------------

@router.post("/debate")
async def debate(req: DebateRequest):
    f = _facade()
    try:
        text, used = await f.maybe_run_debate(
            message=req.message,
            context_messages=req.context_messages,
            preferred_provider=req.preferred_provider,
            images=req.images,
        )
        return {"response": text, "used": used}
    except Exception as e:
        logger.exception("debate failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/spawn")
async def spawn(req: SpawnRequest):
    f = _facade()
    try:
        text, agent_type, provider, meta = await f.maybe_spawn_agent(
            message=req.message,
            context_messages=req.context_messages,
            user_id=req.user_id,
            user_api_keys=req.user_api_keys,
            preferred_provider=req.preferred_provider,
            forced_agent_type=req.forced_agent_type,
            images=req.images,
        )
        return {
            "response": text,
            "agent_type": agent_type,
            "llm_provider": provider,
            "router_metadata": meta,
        }
    except Exception as e:
        logger.exception("spawn failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/team")
async def team(req: TeamRequest):
    f = _facade()
    try:
        return await f.maybe_run_team(
            message=req.message,
            context_messages=req.context_messages,
            team_id=req.team_id,
            user_id=req.user_id,
            preferred_provider=req.preferred_provider,
        )
    except Exception as e:
        logger.exception("team failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/voting")
async def voting(req: VotingRequest):
    f = _facade()
    try:
        return await f.run_voting(
            task=req.task,
            context=req.context,
            agent_types=req.agent_types,
            preferred_provider=req.preferred_provider,
        )
    except Exception as e:
        logger.exception("voting failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/confidence")
async def confidence(req: ConfidenceRequest):
    return _wrap(lambda: _facade().analyze_confidence(req.response, req.task))


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    return _wrap(lambda: _facade().submit_feedback(
        user_id=req.user_id,
        agent_type=req.agent_type,
        rating=req.rating,
        task=req.task,
        response=req.response,
        feedback_text=req.feedback_text,
    ))


@router.get("/feedback/stats")
async def feedback_stats():
    return _wrap(lambda: _facade().get_feedback_stats())


@router.get("/stats")
async def stats():
    return _wrap(lambda: _facade().get_agent_stats())


@router.get("/teams")
async def teams():
    return _wrap(lambda: _facade().get_team_list())


@router.get("/chains")
async def chains(user_id: Optional[str] = None):
    return _wrap(lambda: _facade().get_chain_list(user_id=user_id))


@router.post("/chain/run")
async def chain_run(req: ChainRunRequest):
    f = _facade()
    try:
        return await f.run_chain(
            chain_id=req.chain_id,
            initial_input=req.initial_input,
            user_id=req.user_id,
            preferred_provider=req.preferred_provider,
        )
    except Exception as e:
        logger.exception("chain_run failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/chain/create")
async def chain_create(req: ChainCreateRequest):
    return _wrap(lambda: _facade().create_chain(
        user_id=req.user_id,
        name=req.name,
        steps=req.steps,
        description=req.description,
    ))


@router.post("/validate")
async def validate(req: ValidateRequest):
    f = _facade()
    try:
        return await f.validate_response(
            task=req.task,
            response=req.response,
            context=req.context,
            preferred_provider=req.preferred_provider,
        )
    except Exception as e:
        logger.exception("validate failed")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/citations")
async def citations(req: CitationsRequest):
    return _wrap(lambda: _facade().add_citations(
        response=req.response, task=req.task, agent_type=req.agent_type,
    ))


@router.post("/hallucinations")
async def hallucinations(req: HallucinationRequest):
    return _wrap(lambda: _facade().detect_hallucinations(
        response=req.response, task=req.task,
    ))


@router.post("/project_context/get")
async def project_context_get(req: ProjectContextRead):
    return _wrap(lambda: _facade().get_project_context(req.user_id, req.project_name))


@router.post("/project_context/update")
async def project_context_update(req: ProjectContextWrite):
    return _wrap(lambda: _facade().update_project_context(
        req.user_id, req.project_name, req.context,
    ))

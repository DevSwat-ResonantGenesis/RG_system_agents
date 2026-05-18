# RG_System_Agents

System-level agent orchestration service. Owns the cognitive layer
extracted from `RG_Chat`:

- **Multi-agent debate**, voting, chaining, team composition
- **Autonomous planner & executor**
- **Self-improving agent** feedback loop
- **Decision framework**, task analyzer, capability registry
- **Agent metrics**, confidence, specialization
- **Agent classifier** (ML routing of user requests to system agents)

## Distinct from `RG_Agent_Engine`

| Service | Owns |
|---|---|
| `RG_System_Agents` (this repo) | **System** agents — internal cognition that powers `RG_Chat` responses |
| `RG_Agent_Engine` | **User-published** agents — wallets, custom tools, scheduling, autonomous daemons |

## Canonical wiring

- **LLM**: every call goes through `rg_llm.UnifiedLLMClient` (volume-mounted as `/app/rg_llm`). No chat-side `MultiAIRouter`. Adapter: `app/domain/provider.py`.
- **Memory**: every read/write goes to `RG_Memory` over HTTP (`RG_MEMORY_URL`). Adapter: `app/services/agent_memory.py`.
- **Auth**: internal calls signed with `INTERNAL_SECRET`.

## HTTP surface

```
GET  /health
GET  /

POST /agent/debate
POST /agent/spawn
POST /agent/team
POST /agent/voting
POST /agent/confidence
POST /agent/feedback
GET  /agent/feedback/stats
GET  /agent/stats
GET  /agent/teams
GET  /agent/chains
POST /agent/chain/run
POST /agent/chain/create
POST /agent/validate
POST /agent/citations
POST /agent/hallucinations
POST /agent/project_context/get
POST /agent/project_context/update
```

## Environment

| Var | Default | Purpose |
|---|---|---|
| `RG_MEMORY_URL` | `http://memory_service:8000` | Canonical memory service |
| `INTERNAL_SECRET` | _(unset)_ | Inter-service auth header |
| `PORT` | `8000` | uvicorn port |

## Status

**v0.1 — initial extraction.** Files were ported verbatim from `RG_Chat`
and re-wired to canonical `rg_llm` + `RG_Memory`. The "deback fix wier"
pass — converting individual engines to use `rg_llm` directly instead of
the legacy router shim, normalizing DB models, replacing local in-memory
caches with Redis, etc. — is queued as follow-up work.

# AI Architect Backend

Single unified agent that answers architecture questions and evaluates solution submissions.

## Quick Start

```bash
cd backend
uv sync
cp agt_architect/.env.example agt_architect/.env   # fill OPENROUTER_API_KEY
```

## Agent

### `agt_architect` — Unified AI Architect

One agent with two modes:

1. **Q&A** — answers architecture questions directly (~10s)
2. **Review** — delegates to a review board of Application + Infrastructure Architects, then consolidates their findings into a verdict (~67s)

```
agt_architect (LlmAgent)
├── Answers questions directly (Q&A mode)
└── Calls run_review tool → review board pipeline
    ├── ParallelAgent (review_board)
    │   ├── application_architect     → state["application_review"]
    │   └── infrastructure_architect  → state["infrastructure_review"]
    └── consolidator                  → state["verdict"]
```

Each architect evaluates against principles defined in markdown files under `principles/`. The pipeline writes raw text to session state; the API layer parses it into structured models.

```bash
adk run agt_architect              # CLI mode
```

**Config:** `.env/AGT_ARCHITECT_MODEL` (default: `openrouter/qwen/qwen3.6-flash`)

Recommended fast models via OpenRouter:

| Model | Speed | JSON reliability |
|-------|-------|------------------|
| `qwen/qwen3.6-flash` | ~1-2s | ✅ good |
| `deepseek/deepseek-v4-flash` | ~1-2s | ✅ good |
| `moonshotai/kimi-k2.5` | ~4s | ✅ good |
| `moonshotai/kimi-k2.6` | ~100s | ❌ intermittent |

## FastAPI Layer

Thin wrapper around the ADK Runner with SSE streaming.

```bash
uvicorn api.main:app --reload
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe |
| `/chat` | POST | Send a message (question or solution). Returns `{"session_id": "..."}` |
| `/chat/{id}/stream` | GET | SSE stream of agent response |

### SSE Event Format

```
event: status
data: {"stage": "started", "session_id": "..."}

event: answer
data: {"text": "<direct answer>"}

event: verdict
data: {<Verdict JSON>}
```

Example curl:

```bash
# Q&A
curl -X POST http://localhost:8100/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "What is CQRS?"}'

# Review
curl -X POST http://localhost:8100/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Flask monolith on one EC2, SQLite on local disk, no backups."}'

# Stream results
curl -N http://localhost:8100/chat/<session_id>/stream
```

## Project Structure

```
backend/
├── agt_architect/           # Unified AI Architect agent
│   ├── agent.py             # Root agent with triage logic + review sub-agents
│   ├── tools.py             # RunReviewTool — delegates to review pipeline
│   ├── schemas.py           # Pydantic models: Finding, Review, Verdict
│   ├── principles/          # Architecture principles (loaded into instructions)
│   │   ├── application.md
│   │   └── infrastructure.md
│   └── .env.example         # OPENROUTER_API_KEY template
├── api/                     # FastAPI + SSE wrapper
│   └── main.py              # POST /chat, GET /chat/{id}/stream
├── tests/
│   └── test_agt_architect.py  # 11 offline tests
├── pyproject.toml           # Dependencies: google-adk, litellm, fastapi, uvicorn
└── uv.lock
```

## Testing

```bash
uv run pytest tests/ -q    # all offline, no API key needed
```

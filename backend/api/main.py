"""FastAPI wrapper around the agt_architect unified agent.

Single chatbot with dual responsibilities:
1. Answer architecture questions directly
2. Review submitted solutions via the review board (tool-based delegation)

API contract for the frontend
-----------------------------

POST /chat
    Body: ``{"message": "<architecture question or solution submission>"}``
    Returns: ``{"session_id": "<id>"}`` - use it to open the stream.

GET /chat/{session_id}/stream
    Server-Sent Events stream. Each event has an ``event:`` type and a JSON
    ``data:`` payload:

    - ``event: status``   ``{"stage": "started"}``
    - ``event: answer``   ``{"text": "<direct answer>"}`` - for general questions
    - ``event: verdict``  ``{<Verdict JSON>}`` - for solution reviews
    - ``event: error``    ``{"message": "..."}`` - terminal failure

GET /health
    Liveness probe, returns ``{"status": "ok"}``.

Run from the ``backend/`` directory:

    uvicorn api.main:app --reload
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from agt_architect.agent import root_agent


def _parse_json(text: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    cleaned = re.sub(r"```(?:json)?\s*\n?", "", text).strip()
    return json.loads(cleaned)


APP_NAME = "agt_architect"
USER_ID = "frontend"  # single-user local setup; replace with real auth later

app = FastAPI(title="AI Architect", version="0.1.0")

# Local frontend dev servers (Vite/Next/etc.) - tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="Architecture question or solution to review.")


@dataclass
class ChatJob:
    message: str
    queue: asyncio.Queue[tuple[str, dict] | None] = field(default_factory=asyncio.Queue)


# session_id -> job. Entries are removed once the stream finishes.
_jobs: dict[str, ChatJob] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", status_code=202)
async def create_chat(request: ChatRequest) -> dict[str, str]:
    session_id = uuid.uuid4().hex
    job = ChatJob(message=request.message)
    _jobs[session_id] = job
    asyncio.create_task(_run_chat(session_id, job))
    return {"session_id": session_id}


@app.get("/chat/{session_id}/stream")
async def stream_chat(session_id: str) -> StreamingResponse:
    job = _jobs.get(session_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown or expired session_id")

    async def events():
        try:
            while True:
                item = await job.queue.get()
                if item is None:  # sentinel: done
                    break
                event_type, payload = item
                yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
        finally:
            _jobs.pop(session_id, None)

    return StreamingResponse(events(), media_type="text/event-stream")


async def _run_chat(session_id: str, job: ChatJob) -> None:
    """Run the ADK pipeline, pushing SSE-ready events onto the job queue."""

    async def emit(event_type: str, payload: dict) -> None:
        await job.queue.put((event_type, payload))

    try:
        await emit("status", {"stage": "started", "session_id": session_id})

        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        message = types.Content(
            role="user", parts=[types.Part.from_text(text=job.message)]
        )

        async for event in runner.run_async(
            user_id=USER_ID, session_id=session.id, new_message=message
        ):
            pass

        # Check what state was produced
        final = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session.id
        )
        state = final.state if final else {}

        # If review board ran (state keys indicate tool call), emit structured results
        if "application_review" in state or "verdict" in state:
            from agt_architect.schemas import Review, Verdict

            for key, agent_name in (
                ("application_review", "application_architect"),
                ("infrastructure_review", "infrastructure_architect"),
            ):
                if key in state:
                    try:
                        parsed = _parse_json(state[key])
                        validated = Review.model_validate(parsed)
                        await emit("review", {"agent": agent_name, "review": validated.model_dump()})
                    except Exception as e:
                        await emit("review", {"agent": agent_name, "review": {"raw": state[key], "parse_error": str(e)}})
            if "verdict" in state:
                try:
                    parsed = _parse_json(state["verdict"])
                    validated = Verdict.model_validate(parsed)
                    await emit("verdict", validated.model_dump())
                except Exception as e:
                    await emit("verdict", {"raw": state["verdict"], "parse_error": str(e)})
        else:
            # Direct answer from root agent
            last_content = None
            for e in reversed(final.events if final else []):
                if e.content and e.author == "agt_architect":
                    last_content = e.content
                    break
            if last_content and last_content.parts:
                text = " ".join(p.text or "" for p in last_content.parts if p.text and not p.thought)
                if text.strip():
                    await emit("answer", {"text": text.strip()})
                else:
                    await emit("error", {"message": "Agent produced no output."})
            else:
                await emit("error", {"message": "No response received from agent."})
    except Exception as exc:
        await emit("error", {"message": f"{type(exc).__name__}: {exc}"})
    finally:
        await job.queue.put(None)

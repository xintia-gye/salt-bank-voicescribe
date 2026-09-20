"""Salt Bank VoiceScribe — FastAPI backend.

Serves the operator/supervisor REST API and the built React SPA.

Routes:
  GET  /api/health
  GET  /api/filters
  GET  /api/calls                     (filter: category, language, sentiment, agent, search)
  GET  /api/calls/{call_id}
  POST /api/calls/{call_id}/approve
  GET  /api/stats
  POST /api/ingest/twilio             (Twilio webhook / synthetic replay)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, genie
from .config import get_settings
from .ingest import get_adapter

settings = get_settings()
app = FastAPI(title="Salt Bank VoiceScribe", version="1.0.0")

# CORS for local Vite dev server (proxy also handles this in vite.config).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class ApproveRequest(BaseModel):
    action: str = "approve"          # "approve" | "edit"
    edited_summary: str | None = None
    approved_by: str | None = None


class GenieRequest(BaseModel):
    question: str
    conversation_id: str | None = None


# --------------------------------------------------------------------------
# API routes
# --------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "db_configured": settings.db_configured,
        "ingest_adapter": settings.ingest_adapter,
        "is_databricks_app": settings.is_databricks_app,
    }


@app.get("/api/filters")
def filters():
    try:
        return db.get_filter_options()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"warehouse error: {exc}") from exc


@app.get("/api/calls")
def list_calls(
    category: str | None = Query(None),
    language: str | None = Query(None),
    sentiment: str | None = Query(None),
    agent: str | None = Query(None),
    search: str | None = Query(None),
):
    try:
        return db.list_calls(
            {
                "category": category,
                "language": language,
                "sentiment": sentiment,
                "agent": agent,
                "search": search,
            }
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"warehouse error: {exc}") from exc


@app.get("/api/calls/{call_id}")
def get_call(call_id: str):
    try:
        row = db.get_call(call_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"warehouse error: {exc}") from exc
    if not row:
        raise HTTPException(status_code=404, detail="call not found")
    return row


@app.post("/api/calls/{call_id}/approve")
def approve_call(call_id: str, body: ApproveRequest):
    status = "approved" if body.action == "approve" else "edited"
    record = db.set_approval(
        call_id, status, body.edited_summary, body.approved_by
    )
    return {"call_id": call_id, **record}


@app.get("/api/stats")
def stats():
    try:
        return db.get_stats()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"warehouse error: {exc}") from exc


@app.get("/api/genie/info")
def genie_info():
    return {
        "space_id": genie.get_space_id(),
        "sample_questions": [
            "How many calls did we have by category?",
            "What is the average call duration by agent, in minutes?",
            "Show the share of negative-sentiment calls by language.",
            "Which agent handled the most account closure calls?",
        ],
    }


@app.post("/api/genie/ask")
def genie_ask(body: GenieRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    try:
        return genie.ask(body.question, body.conversation_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"genie error: {exc}") from exc


@app.post("/api/ingest/twilio")
async def ingest_twilio(request: Request):
    """Accept a Twilio recording webhook (twilio mode) or replay a synthetic
    call (synthetic mode, default). Inserts a bronze_calls row and returns the
    normalised call payload."""
    adapter = get_adapter()
    form = dict((await request.form()).items())  # type: ignore[arg-type]
    headers = {k.lower(): v for k, v in request.headers.items()}
    url = str(request.url)

    try:
        adapter.validate(url=url, form=form, headers=headers)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = adapter.parse(form=form)

    inserted = False
    warning = None
    if settings.db_configured:
        try:
            _insert_bronze(payload)
            inserted = True
        except Exception as exc:  # noqa: BLE001
            warning = f"bronze insert skipped: {exc}"

    return JSONResponse(
        {
            "adapter": adapter.name,
            "inserted_bronze": inserted,
            "warning": warning,
            "call": payload.to_public(),
        }
    )


def _insert_bronze(payload) -> None:
    """Best-effort insert into bronze_calls. Column set matches the known
    metadata; if the table schema differs the caller surfaces a warning."""
    db.execute(
        """
        INSERT INTO bronze_calls
            (call_id, agent, from_number, to_number, language,
             duration_seconds, started_at, recording_uri, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            payload.call_id,
            payload.agent,
            payload.from_number,
            payload.to_number,
            payload.language,
            payload.duration_seconds,
            payload.started_at,
            payload.recording_uri,
            payload.source,
        ],
    )


# --------------------------------------------------------------------------
# Static SPA (built React app in frontend/dist)
# --------------------------------------------------------------------------
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    if (_FRONTEND_DIST / "assets").is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=_FRONTEND_DIST / "assets"),
            name="assets",
        )

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("DEV_RELOAD")),
    )

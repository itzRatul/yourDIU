"""
PDF Chat API
============
Lets logged-in users upload a PDF and chat with it using RAG.
Completely separate from the main DIU assistant chat.

Design:
  - PDFs are TEMPORARY (7-day TTL) — for research, not archival
  - Raw PDF bytes are discarded after processing; only chunks + embeddings persist
  - AI answers ONLY from the PDF content — no training data leakage
  - Even if the AI "knows" the answer from training, it will NOT answer unless
    that information is present in the uploaded PDF
  - Web search is a SEPARATE explicit user action (allow_web_search=True)
  - Chat history is client-side (passed in request body, not stored server-side)

Endpoints:
  POST   /pdf-chat/sessions                      — upload PDF, start processing
  GET    /pdf-chat/sessions                      — list user's active sessions
  GET    /pdf-chat/sessions/{id}                 — get session details (poll for status)
  DELETE /pdf-chat/sessions/{id}                 — delete session + all chunks immediately
  POST   /pdf-chat/sessions/{id}/summarize       — generate & cache PDF summary
  POST   /pdf-chat/sessions/{id}/chat            — SSE streaming chat with PDF
  POST   /pdf-chat/sessions/{id}/chat/sync       — sync chat (for testing / mobile)

SSE event types (chat endpoint):
  {"type": "meta",  "mode": "pdf_rag|pdf_search|not_found", "session_id": "..."}
  {"type": "chunk", "content": "..."}
  {"type": "done"}
  {"type": "error", "message": "..."}

mode values:
  pdf_rag    — answered from PDF content
  pdf_search — PDF + web search (user explicitly sent allow_web_search=true)
  not_found  — answer not found in PDF (AI says so directly, no web search prompt)
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.core.security import get_current_user
from app.core.supabase import supabase_admin
from app.services.pdf.pdf_processor import process_pdf
from app.services.pdf.pdf_brain import get_pdf_answer, generate_pdf_summary

logger = logging.getLogger("yourDIU.api.pdf_chat")
router = APIRouter(prefix="/pdf-chat", tags=["PDF Chat"])

_MAX_FILE_SIZE_MB = 20
_MAX_FILE_SIZE_BYTES = _MAX_FILE_SIZE_MB * 1024 * 1024


# ── Models ────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:    str    # "user" | "assistant"
    content: str


class PDFChatRequest(BaseModel):
    message:          str
    history:          list[ChatMessage] = []
    allow_web_search: bool              = False

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty.")
        return v.strip()

    @field_validator("history")
    @classmethod
    def limit_history(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        # Keep last 20 turns to avoid context overflow
        return v[-20:]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: str, user_id: str) -> dict:
    resp = (
        supabase_admin.table("pdf_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="PDF session not found.")
    return resp.data


def _assert_ready(session: dict):
    if session["status"] == "processing":
        raise HTTPException(status_code=202, detail="PDF is still being processed. Please wait.")
    if session["status"] == "failed":
        raise HTTPException(status_code=422, detail="PDF processing failed. Try uploading again.")


def _history_to_dicts(history: list[ChatMessage]) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in history]


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/sessions", summary="Upload a PDF and create a chat session")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file:             UploadFile       = File(...),
    current_user     = Depends(get_current_user),
):
    """
    Upload a PDF file. Processing (chunking + embedding) runs in the background.
    Returns the session immediately with status='processing'.
    Poll GET /sessions/{id} until status='ready' before chatting.
    """
    # Validate file type
    ct = file.content_type or ""
    if ct not in ("application/pdf", "application/octet-stream") and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()

    if len(file_bytes) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {_MAX_FILE_SIZE_MB} MB.",
        )
    if len(file_bytes) < 100:
        raise HTTPException(status_code=400, detail="File appears to be empty.")

    # Create session record immediately
    session_id = str(uuid.uuid4())
    supabase_admin.table("pdf_sessions").insert({
        "id":        session_id,
        "user_id":   current_user.id,
        "filename":  file.filename or "document.pdf",
        "file_size": len(file_bytes),
        "status":    "processing",
    }).execute()

    # Process in background — client polls for status
    background_tasks.add_task(
        process_pdf,
        file_bytes=file_bytes,
        filename=file.filename or "document.pdf",
        session_id=session_id,
    )

    logger.info(
        "PDF upload: user=%s session=%s file=%s size=%dKB",
        current_user.id, session_id, file.filename, len(file_bytes) // 1024,
    )

    return {
        "session_id": session_id,
        "status":     "processing",
        "filename":   file.filename,
        "message":    "PDF is being processed. Poll GET /pdf-chat/sessions/{id} until status is 'ready'.",
    }


# ── Session management ────────────────────────────────────────────────────────

@router.get("/sessions", summary="List active PDF sessions for current user")
async def list_sessions(
    limit:        int  = Query(default=10, le=50),
    offset:       int  = Query(default=0),
    current_user = Depends(get_current_user),
):
    resp = (
        supabase_admin.table("pdf_sessions")
        .select("id, filename, file_size, page_count, chunk_count, status, summary, expires_at, created_at")
        .eq("user_id", current_user.id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    sessions = resp.data or []
    # Include a has_summary flag for UI
    for s in sessions:
        s["has_summary"] = bool(s.get("summary"))
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/sessions/{session_id}", summary="Get PDF session details (poll for processing status)")
async def get_session(
    session_id:  str,
    current_user = Depends(get_current_user),
):
    session = _get_session_or_404(session_id, current_user.id)
    session["has_summary"] = bool(session.get("summary"))
    return session


@router.delete("/sessions/{session_id}", summary="Delete a PDF session and all its chunks")
async def delete_session(
    session_id:  str,
    current_user = Depends(get_current_user),
):
    _get_session_or_404(session_id, current_user.id)

    # Cascade delete removes pdf_session_chunks automatically (FK on delete cascade)
    supabase_admin.table("pdf_sessions").delete().eq("id", session_id).execute()

    logger.info("PDF session deleted: session=%s user=%s", session_id, current_user.id)
    return {"message": "PDF session deleted."}


# ── Summary ───────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/summarize", summary="Generate a structured summary of the PDF")
async def summarize_pdf(
    session_id:  str,
    current_user = Depends(get_current_user),
):
    """
    Generates a comprehensive summary using the full PDF content.
    The summary is cached in the session row — subsequent calls return the cache.
    """
    session = _get_session_or_404(session_id, current_user.id)
    _assert_ready(session)

    # Return cached summary if available
    if session.get("summary"):
        return {"summary": session["summary"], "cached": True}

    summary = await generate_pdf_summary(session_id)

    # Cache the summary
    supabase_admin.table("pdf_sessions").update(
        {"summary": summary}
    ).eq("id", session_id).execute()

    return {"summary": summary, "cached": False}


# ── Chat (SSE streaming) ──────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/chat", summary="Chat with PDF (SSE streaming)")
async def chat_with_pdf(
    session_id:  str,
    body:        PDFChatRequest,
    current_user = Depends(get_current_user),
):
    """
    Stream AI responses grounded in the uploaded PDF.

    The AI will ONLY answer from the uploaded PDF content.
    If the answer is not in the PDF, it will say so directly — it will NOT
    answer from general knowledge even if it "knows" the answer.

    To also search the web, send allow_web_search=true (explicit user action).

    SSE event format:
      data: {"type": "meta",  "mode": "pdf_rag|pdf_search|not_found", "session_id": "..."}
      data: {"type": "chunk", "content": "..."}
      data: {"type": "done"}
      data: {"type": "error", "message": "..."}
    """
    session = _get_session_or_404(session_id, current_user.id)
    _assert_ready(session)

    history = _history_to_dicts(body.history)

    async def event_stream():
        try:
            gen, mode = await get_pdf_answer(
                session_id       = session_id,
                query            = body.message,
                history          = history,
                allow_web_search = body.allow_web_search,
                stream           = True,
            )

            # Send meta first (mode tells frontend if answer came from PDF, web, or not found)
            yield _sse({"type": "meta", "mode": mode, "session_id": session_id})

            # Stream the answer (or the "not found" message)
            async for chunk_text in gen:
                yield _sse({"type": "chunk", "content": chunk_text})

            yield _sse({"type": "done"})

        except Exception as exc:
            logger.error("PDF chat SSE error: %s", exc)
            yield _sse({"type": "error", "message": "An error occurred. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":              "no-cache",
            "X-Accel-Buffering":          "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Chat (sync) ───────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/chat/sync", summary="Chat with PDF (sync response)")
async def chat_with_pdf_sync(
    session_id:  str,
    body:        PDFChatRequest,
    current_user = Depends(get_current_user),
):
    """
    Synchronous version of PDF chat. Returns complete answer in one response.
    Use for testing or clients that don't support SSE.
    """
    session = _get_session_or_404(session_id, current_user.id)
    _assert_ready(session)

    history = _history_to_dicts(body.history)

    answer, mode = await get_pdf_answer(
        session_id       = session_id,
        query            = body.message,
        history          = history,
        allow_web_search = body.allow_web_search,
        stream           = False,
    )

    return {
        "answer":     answer,
        "mode":       mode,        # "pdf_rag" | "pdf_search" | "not_found"
        "session_id": session_id,
    }


# ── Utility ───────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

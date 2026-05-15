"""
Chat API
========
Endpoints:
  POST /chat/message          — send a message, get streaming SSE response
  POST /chat/message/sync     — send a message, get full response (non-streaming)
  GET  /chat/sessions         — list user's chat sessions
  GET  /chat/sessions/{id}    — get one session with all messages
  POST /chat/sessions         — create a new session
  DELETE /chat/sessions/{id}  — delete a session

Guest users (no token) can chat but history is NOT saved.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user, get_optional_user
from app.core.supabase import supabase_admin
from app.models.chat import ChatMessageCreate, SessionCreate
from app.services.ai.brain_service import get_answer
from app.services.search.tavily_service import get_tavily_usage

logger = logging.getLogger("yourDIU.api.chat")
router = APIRouter(prefix="/chat", tags=["Chat"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_history(session_id: str, limit: int = 20) -> list[dict]:
    """Load recent chat history from Supabase for context injection."""
    resp = (
        supabase_admin.table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    messages = resp.data or []
    # Reverse to chronological order
    messages.reverse()
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def _save_message(session_id: str, role: str, content: str) -> dict:
    """Save a chat message to Supabase."""
    resp = (
        supabase_admin.table("chat_messages")
        .insert({
            "id":         str(uuid.uuid4()),
            "session_id": session_id,
            "role":       role,
            "content":    content,
        })
        .execute()
    )
    return resp.data[0] if resp.data else {}


def _ensure_session(user_id: str, session_id: Optional[str], first_message: str) -> str:
    """Get existing session or create a new one. Returns session_id."""
    if session_id:
        # Verify session belongs to user
        resp = (
            supabase_admin.table("chat_sessions")
            .select("id")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if resp.data:
            return session_id

    # Create new session with auto-generated title
    title = first_message[:60] + ("…" if len(first_message) > 60 else "")
    resp = (
        supabase_admin.table("chat_sessions")
        .insert({
            "id":      str(uuid.uuid4()),
            "user_id": user_id,
            "title":   title,
        })
        .execute()
    )
    return resp.data[0]["id"]


def _update_session_timestamp(session_id: str):
    """Touch updated_at on the session."""
    supabase_admin.table("chat_sessions").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", session_id).execute()


# ── Streaming endpoint ───────────────────────────────────────────────────────

@router.post("/message", summary="Send message — streaming SSE response")
async def chat_message_stream(
    body: ChatMessageCreate,
    current_user=Depends(get_optional_user),
):
    """
    Stream the AI response as Server-Sent Events.
    Guest users: no history saved.
    Logged-in users: history loaded + response saved.
    """
    is_guest = current_user is None
    history = []
    session_id = None

    if not is_guest:
        session_id = _ensure_session(current_user.id, body.session_id, body.message)
        history = _load_history(session_id)
        _save_message(session_id, "user", body.message)

    stream_gen, mode, sources = await get_answer(
        query=body.message,
        history=history,
        stream=True,
    )

    async def event_stream() -> AsyncIterator[str]:
        full_response = []

        # Send metadata first
        meta = json.dumps({
            "type":       "meta",
            "session_id": session_id,
            "mode":       mode,
            "sources":    sources[:3],  # first 3 sources only
        })
        yield f"data: {meta}\n\n"

        # Stream text chunks
        async for chunk in stream_gen:
            full_response.append(chunk)
            payload = json.dumps({"type": "chunk", "text": chunk})
            yield f"data: {payload}\n\n"

        # Done signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # Save assistant response if logged in
        if not is_guest and session_id:
            answer = "".join(full_response)
            _save_message(session_id, "assistant", answer)
            _update_session_timestamp(session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Sync endpoint (for testing / simple clients) ─────────────────────────────

@router.post("/message/sync", summary="Send message — full response (non-streaming)")
async def chat_message_sync(
    body: ChatMessageCreate,
    current_user=Depends(get_optional_user),
):
    is_guest = current_user is None
    history = []
    session_id = None

    if not is_guest:
        session_id = _ensure_session(current_user.id, body.session_id, body.message)
        history = _load_history(session_id)
        _save_message(session_id, "user", body.message)

    answer, mode, sources = await get_answer(
        query=body.message,
        history=history,
        stream=False,
    )

    if not is_guest and session_id:
        _save_message(session_id, "assistant", answer)
        _update_session_timestamp(session_id)

    return {
        "session_id": session_id,
        "answer":     answer,
        "mode":       mode,
        "sources":    sources[:3],
    }


# ── Session management ───────────────────────────────────────────────────────

@router.get("/sessions", summary="List user's chat sessions")
async def list_sessions(
    limit:  int = Query(default=20, le=50),
    offset: int = Query(default=0),
    current_user=Depends(get_current_user),
):
    resp = (
        supabase_admin.table("chat_sessions")
        .select("id, title, created_at, updated_at")
        .eq("user_id", current_user.id)
        .order("updated_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return {"sessions": resp.data or [], "count": len(resp.data or [])}


@router.get("/sessions/{session_id}", summary="Get a session with all messages")
async def get_session(
    session_id: str,
    current_user=Depends(get_current_user),
):
    session_resp = (
        supabase_admin.table("chat_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", current_user.id)
        .single()
        .execute()
    )
    if not session_resp.data:
        raise HTTPException(status_code=404, detail="Session not found.")

    messages_resp = (
        supabase_admin.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )

    return {
        "session":  session_resp.data,
        "messages": messages_resp.data or [],
        "count":    len(messages_resp.data or []),
    }


@router.post("/sessions", summary="Create a new chat session")
async def create_session(
    body: SessionCreate,
    current_user=Depends(get_current_user),
):
    resp = (
        supabase_admin.table("chat_sessions")
        .insert({
            "id":      str(uuid.uuid4()),
            "user_id": current_user.id,
            "title":   body.title or "New Chat",
        })
        .execute()
    )
    return resp.data[0]


@router.delete("/sessions/{session_id}", summary="Delete a chat session")
async def delete_session(
    session_id: str,
    current_user=Depends(get_current_user),
):
    # Verify ownership
    existing = (
        supabase_admin.table("chat_sessions")
        .select("id")
        .eq("id", session_id)
        .eq("user_id", current_user.id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Messages are deleted via CASCADE in the DB
    supabase_admin.table("chat_sessions").delete().eq("id", session_id).execute()
    return {"message": "Session deleted."}


# ── Debug: search usage stats ─────────────────────────────────────────────────

@router.get("/debug/search-usage", summary="Check Tavily daily usage (admin)")
async def search_usage(_admin=Depends(get_current_user)):
    return get_tavily_usage()

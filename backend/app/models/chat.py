from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class ChatMessageCreate(BaseModel):
    message: str
    session_id: Optional[str] = None   # None → create new session


class ChatMessageResponse(BaseModel):
    session_id: str
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class SessionCreate(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: Optional[float] = None


class AIResponse(BaseModel):
    answer: str
    sources: list[SearchResult] = []
    mode: Literal["rag", "search", "direct", "routine", "teacher"]
    tokens_used: Optional[int] = None

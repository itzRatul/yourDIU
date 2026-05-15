"""
Community API
=============
Endpoints:
  GET    /community/posts              — list posts (paginated, filterable)
  POST   /community/posts              — create post
  GET    /community/posts/{id}         — get one post with comments
  DELETE /community/posts/{id}         — delete post (owner or admin)
  POST   /community/posts/{id}/react   — add/toggle reaction (like, love, etc.)
  POST   /community/posts/{id}/comments        — add comment
  DELETE /community/posts/{id}/comments/{cid}  — delete comment (owner or admin)

Teacher posts get a ⭐ star badge in the frontend.
Teacher comments are pinned to the top (sorted by role, then created_at).
"""

import logging
import uuid
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator

from app.core.security import get_current_user, get_optional_user
from app.core.supabase import supabase_admin

logger = logging.getLogger("yourDIU.api.community")
router = APIRouter(prefix="/community", tags=["Community"])

ALLOWED_REACTIONS = {"like", "love", "haha", "wow", "sad", "angry"}


# ── Models ───────────────────────────────────────────────────────────────────

class PostCreate(BaseModel):
    content:  str
    category: Optional[str] = None   # "general" | "question" | "resource" | "event"
    image_url: Optional[str] = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Post content cannot be empty.")
        if len(v) > 5000:
            raise ValueError("Post content too long (max 5000 chars).")
        return v.strip()


class CommentCreate(BaseModel):
    content:   str
    parent_id: Optional[str] = None   # for threaded replies

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Comment cannot be empty.")
        if len(v) > 2000:
            raise ValueError("Comment too long (max 2000 chars).")
        return v.strip()


class ReactionToggle(BaseModel):
    reaction: str

    @field_validator("reaction")
    @classmethod
    def valid_reaction(cls, v: str) -> str:
        if v not in ALLOWED_REACTIONS:
            raise ValueError(f"Reaction must be one of: {', '.join(ALLOWED_REACTIONS)}")
        return v


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_user_role(user_id: str) -> str:
    resp = (
        supabase_admin.table("profiles")
        .select("role")
        .eq("id", user_id)
        .single()
        .execute()
    )
    return resp.data.get("role", "student") if resp.data else "student"


def _is_admin(user_id: str) -> bool:
    return _get_user_role(user_id) == "admin"


# ── Posts ────────────────────────────────────────────────────────────────────

@router.get("/posts", summary="List community posts")
async def list_posts(
    category: Optional[str] = Query(None),
    limit:    int           = Query(default=20, le=50),
    offset:   int           = Query(default=0),
    _user=Depends(get_optional_user),
):
    query = (
        supabase_admin.table("community_posts")
        .select(
            "*, "
            "profiles!community_posts_user_id_fkey(full_name, avatar_url, role)"
        )
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if category:
        query = query.eq("category", category)

    resp = query.execute()
    return {"posts": resp.data or [], "count": len(resp.data or [])}


@router.post("/posts", summary="Create a community post")
async def create_post(
    body: PostCreate,
    current_user=Depends(get_current_user),
):
    role = _get_user_role(current_user.id)
    post_id = str(uuid.uuid4())

    resp = (
        supabase_admin.table("community_posts")
        .insert({
            "id":        post_id,
            "user_id":   current_user.id,
            "content":   body.content,
            "category":  body.category or "general",
            "image_url": body.image_url,
            "is_teacher_post": role == "teacher",
        })
        .execute()
    )
    return {"post": resp.data[0], "message": "Post created."}


@router.get("/posts/{post_id}", summary="Get a post with its comments")
async def get_post(
    post_id: str,
    _user=Depends(get_optional_user),
):
    post_resp = (
        supabase_admin.table("community_posts")
        .select("*, profiles!community_posts_user_id_fkey(full_name, avatar_url, role)")
        .eq("id", post_id)
        .single()
        .execute()
    )
    if not post_resp.data:
        raise HTTPException(status_code=404, detail="Post not found.")

    # Comments: teacher comments first (pinned), then by created_at
    comments_resp = (
        supabase_admin.table("post_comments")
        .select("*, profiles!post_comments_user_id_fkey(full_name, avatar_url, role)")
        .eq("post_id", post_id)
        .order("created_at")
        .execute()
    )
    comments = comments_resp.data or []

    # Pin teacher/admin comments to top
    teacher_comments = [c for c in comments if c.get("profiles", {}).get("role") in ("teacher", "admin")]
    other_comments   = [c for c in comments if c.get("profiles", {}).get("role") not in ("teacher", "admin")]
    sorted_comments  = teacher_comments + other_comments

    # Reaction counts
    reactions_resp = (
        supabase_admin.table("post_reactions")
        .select("reaction")
        .eq("post_id", post_id)
        .execute()
    )
    reaction_counts: dict[str, int] = {}
    for r in (reactions_resp.data or []):
        reaction_counts[r["reaction"]] = reaction_counts.get(r["reaction"], 0) + 1

    return {
        "post":             post_resp.data,
        "comments":         sorted_comments,
        "comments_count":   len(sorted_comments),
        "reaction_counts":  reaction_counts,
    }


@router.delete("/posts/{post_id}", summary="Delete a post (owner or admin)")
async def delete_post(
    post_id:      str,
    current_user=Depends(get_current_user),
):
    existing = (
        supabase_admin.table("community_posts")
        .select("user_id")
        .eq("id", post_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Post not found.")

    if existing.data["user_id"] != current_user.id and not _is_admin(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    supabase_admin.table("community_posts").delete().eq("id", post_id).execute()
    return {"message": "Post deleted."}


# ── Reactions ────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/react", summary="Toggle a reaction on a post")
async def react_to_post(
    post_id:      str,
    body:         ReactionToggle,
    current_user=Depends(get_current_user),
):
    # Check if user already reacted with this type
    existing = (
        supabase_admin.table("post_reactions")
        .select("id")
        .eq("post_id", post_id)
        .eq("user_id", current_user.id)
        .eq("reaction", body.reaction)
        .execute()
    )

    if existing.data:
        # Toggle off
        supabase_admin.table("post_reactions").delete().eq("id", existing.data[0]["id"]).execute()
        return {"action": "removed", "reaction": body.reaction}
    else:
        # Add reaction (remove any previous different reaction first)
        supabase_admin.table("post_reactions").delete().eq("post_id", post_id).eq("user_id", current_user.id).execute()
        supabase_admin.table("post_reactions").insert({
            "id":       str(uuid.uuid4()),
            "post_id":  post_id,
            "user_id":  current_user.id,
            "reaction": body.reaction,
        }).execute()
        return {"action": "added", "reaction": body.reaction}


# ── Comments ─────────────────────────────────────────────────────────────────

@router.post("/posts/{post_id}/comments", summary="Add a comment to a post")
async def add_comment(
    post_id:      str,
    body:         CommentCreate,
    current_user=Depends(get_current_user),
):
    # Verify post exists
    post = (
        supabase_admin.table("community_posts")
        .select("id")
        .eq("id", post_id)
        .single()
        .execute()
    )
    if not post.data:
        raise HTTPException(status_code=404, detail="Post not found.")

    role = _get_user_role(current_user.id)
    resp = (
        supabase_admin.table("post_comments")
        .insert({
            "id":                str(uuid.uuid4()),
            "post_id":           post_id,
            "user_id":           current_user.id,
            "content":           body.content,
            "parent_id":         body.parent_id,
            "is_teacher_comment": role in ("teacher", "admin"),
        })
        .execute()
    )
    return {"comment": resp.data[0], "message": "Comment added."}


@router.delete(
    "/posts/{post_id}/comments/{comment_id}",
    summary="Delete a comment (owner or admin)",
)
async def delete_comment(
    post_id:    str,
    comment_id: str,
    current_user=Depends(get_current_user),
):
    existing = (
        supabase_admin.table("post_comments")
        .select("user_id")
        .eq("id", comment_id)
        .eq("post_id", post_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Comment not found.")

    if existing.data["user_id"] != current_user.id and not _is_admin(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized.")

    supabase_admin.table("post_comments").delete().eq("id", comment_id).execute()
    return {"message": "Comment deleted."}

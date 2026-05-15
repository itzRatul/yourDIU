from fastapi import Depends, HTTPException, status, Header
from typing import Optional
from .supabase import supabase_admin
from .config import settings

ALLOWED_DOMAIN = "diu.edu.bd"


def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def _get_auth_user(authorization: Optional[str] = Header(None, alias="Authorization")):
    """Verify Supabase JWT and return the auth user. Returns None for guests."""
    token = _extract_token(authorization)
    if not token:
        return None
    try:
        resp = supabase_admin.auth.get_user(token)
        return resp.user
    except Exception:
        return None


async def get_current_user(auth_user=Depends(_get_auth_user)):
    """Require authenticated @diu.edu.bd user. Raises 401/403 otherwise."""
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in.",
        )
    email: str = auth_user.email or ""
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only @{ALLOWED_DOMAIN} accounts are allowed.",
        )
    return auth_user


async def get_optional_user(auth_user=Depends(_get_auth_user)):
    """Allow guests (returns None) and authenticated users (returns user)."""
    return auth_user


async def require_role(*roles: str):
    """Factory: returns a dependency that checks the user's role in profiles table."""
    async def _check(current_user=Depends(get_current_user)):
        from .supabase import supabase_admin
        resp = (
            supabase_admin.table("profiles")
            .select("role")
            .eq("id", current_user.id)
            .single()
            .execute()
        )
        user_role = resp.data.get("role", "student") if resp.data else "student"
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(roles)}",
            )
        return current_user
    return _check

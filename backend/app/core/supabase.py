from supabase import create_client, Client
from .config import settings


def _make_client(key: str) -> Client:
    if not settings.supabase_url or not key:
        raise RuntimeError(
            "SUPABASE_URL and key must be set in .env before starting the server."
        )
    return create_client(settings.supabase_url, key)


# Anon client — respects RLS, safe to use for user-scoped queries
supabase: Client = _make_client(settings.supabase_anon_key)

# Service role client — bypasses RLS, backend-only, never exposed to frontend
supabase_admin: Client = _make_client(settings.supabase_service_role_key)

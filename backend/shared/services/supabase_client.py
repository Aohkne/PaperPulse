"""Supabase client — singleton via lru_cache."""

from functools import lru_cache

from backend.config import get_settings
from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in environment")
    return create_client(settings.supabase_url, settings.supabase_key)


def authed_client(token: str) -> Client:
    """Create a per-request Supabase client with user JWT (for RLS)."""
    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_key)
    client.postgrest.auth(token)
    return client

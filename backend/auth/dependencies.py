"""FastAPI dependencies for Supabase Auth JWT verification."""

from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import Any

import httpx
import jwt as pyjwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import get_settings

log = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)


def _decode_supabase_jwt(token: str) -> dict:
    """Decode Supabase JWT payload without signature verification."""
    return pyjwt.decode(
        token,
        options={"verify_signature": False},
        algorithms=["HS256", "RS256", "ES256"],
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
) -> Any:
    """Require a valid Supabase JWT. Raises 401 if missing or invalid."""
    try:
        payload = _decode_supabase_jwt(credentials.credentials)
        if time.time() > payload.get("exp", 0):
            raise HTTPException(status_code=401, detail="Token expired")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")
        return SimpleNamespace(id=user_id, email=payload.get("email", ""))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> Any:
    """Raises 403 if the authenticated user does not have role='admin'.

    Uses httpx directly to call PostgREST — avoids supabase-py client
    incompatibility with the sb_publishable_... key format (PGRST301).
    """
    settings = get_settings()
    token = credentials.credentials

    # Prefer service role key — bypasses RLS, always works server-side.
    # Fall back to the user token if service key not configured.
    api_key = settings.supabase_service_key or settings.supabase_key
    auth_header = f"Bearer {api_key}" if settings.supabase_service_key else f"Bearer {token}"

    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                params={"select": "role", "id": f"eq.{user.id}", "limit": "1"},
                headers={
                    "apikey": api_key,
                    "Authorization": auth_header,
                },
                timeout=5.0,
            )
        log.warning("ADMIN CHECK user=%s status=%s body=%s", user.id, res.status_code, res.text[:300])
        data = res.json() if res.status_code == 200 else []
    except Exception as exc:
        log.warning("ADMIN CHECK exception: %s", exc)
        data = []

    if not data or data[0].get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return user


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_optional),
) -> Any | None:
    """Return the authenticated user if a valid JWT is present, otherwise None."""
    if credentials is None:
        return None
    try:
        payload = _decode_supabase_jwt(credentials.credentials)
        if time.time() > payload.get("exp", 0):
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        return SimpleNamespace(id=user_id, email=payload.get("email", ""))
    except Exception:
        return None

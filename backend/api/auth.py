"""Auth endpoints — register, login, logout, refresh, me."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase_auth.errors import AuthApiError

from backend.auth.dependencies import get_current_user
from backend.config import get_settings
from backend.shared.services.supabase_client import get_supabase_client
from supabase import Client

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


# ── helpers ───────────────────────────────────────────────────────────────────

async def _log_event(
    user_id: str,
    email: str,
    event_type: str,
    ip: str | None,
) -> None:
    """Insert a row into login_logs using the service key (bypasses sb_publishable_ limitation)."""
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{settings.supabase_url}/rest/v1/login_logs",
                json={"user_id": user_id, "email": email, "event_type": event_type, "ip_address": ip},
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                timeout=5.0,
            )
        if res.status_code not in (200, 201, 204):
            log.warning("_log_event %s status=%s body=%s", event_type, res.status_code, res.text[:200])
    except Exception as exc:
        log.warning("_log_event %s failed: %s", event_type, exc)


# ── models ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    redirect_to: str | None = None


class GoogleLoginRequest(BaseModel):
    id_token: str
    nonce: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str | None
    role: str = "user"


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    request: Request,
    body: RegisterRequest,
    supabase: Client = Depends(get_supabase_client),
):
    """Create a new account. Returns tokens immediately if email confirmation is disabled."""
    try:
        sign_up_data: dict = {"email": body.email, "password": body.password}
        if body.redirect_to:
            sign_up_data["options"] = {"email_redirect_to": body.redirect_to}
        res = supabase.auth.sign_up(sign_up_data)
    except AuthApiError as e:
        if e.code == "over_email_send_rate_limit":
            raise HTTPException(
                status_code=429,
                detail="Too many verification emails requested for this address — please wait a few minutes before trying again.",
            ) from e
        raise HTTPException(status_code=400, detail=e.message) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if res.user is None:
        raise HTTPException(status_code=400, detail="Registration failed")

    if res.session is None:
        raise HTTPException(
            status_code=202,
            detail="Check your email to confirm your account before logging in.",
        )

    ip = request.client.host if request.client else None
    await _log_event(str(res.user.id), res.user.email, "register", ip)

    return TokenResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        expires_in=res.session.expires_in,
    )


@router.post("/google", response_model=TokenResponse)
async def google_login(
    request: Request,
    body: GoogleLoginRequest,
    supabase: Client = Depends(get_supabase_client),
):
    """Exchange a Google Identity Services ID token for a PaperPulse session.

    Supabase validates the token's signature/audience itself (the Google
    provider must be enabled in the Supabase dashboard) and auto-creates the
    auth.users row on first sign-in, so this covers both login and signup.
    """
    try:
        res = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": body.id_token,
            "nonce": body.nonce,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if res.session is None or res.user is None:
        raise HTTPException(status_code=400, detail="Google sign-in failed")

    ip = request.client.host if request.client else None
    await _log_event(str(res.user.id), res.user.email, "google_login", ip)

    return TokenResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        expires_in=res.session.expires_in,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    supabase: Client = Depends(get_supabase_client),
):
    """Authenticate with email + password. Returns access_token and refresh_token."""
    try:
        res = supabase.auth.sign_in_with_password({"email": body.email, "password": body.password})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if res.session is None:
        raise HTTPException(status_code=401, detail="Authentication failed")

    ip = request.client.host if request.client else None
    await _log_event(str(res.user.id), res.user.email, "login", ip)

    return TokenResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        expires_in=res.session.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, supabase: Client = Depends(get_supabase_client)):
    """Exchange a refresh_token for a new access_token + refresh_token pair."""
    try:
        res = supabase.auth.refresh_session(body.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    if res.session is None:
        raise HTTPException(status_code=401, detail="Token refresh failed")

    return TokenResponse(
        access_token=res.session.access_token,
        refresh_token=res.session.refresh_token,
        expires_in=res.session.expires_in,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user=Depends(get_current_user),
):
    """Invalidate the current session server-side and log the logout event."""
    token = credentials.credentials
    settings = get_settings()

    # Log logout event
    ip = request.client.host if request.client else None
    await _log_event(str(user.id), user.email, "logout", ip)

    # Revoke session at Supabase GoTrue
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.supabase_url}/auth/v1/logout",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_key,
                },
                timeout=5.0,
            )
    except Exception:
        pass  # best-effort — client discards tokens regardless


@router.get("/me", response_model=UserResponse)
async def me(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user=Depends(get_current_user),
):
    """Return the authenticated user's profile including role."""
    settings = get_settings()
    key = settings.supabase_service_key or settings.supabase_key
    role = "user"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                params={"select": "role", "id": f"eq.{user.id}", "limit": "1"},
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                timeout=5.0,
            )
        if res.status_code == 200 and res.json():
            role = res.json()[0].get("role", "user")
    except Exception:
        pass
    return UserResponse(id=str(user.id), email=user.email, role=role)

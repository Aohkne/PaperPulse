"""Memory / personalization API — user custom instructions.

Backs the "What should PaperPulse call you?" form in the app's General tab
(proactive-agent.html §W0, source='user'). GET loads the saved values; PUT
upserts them. Injected into the research greeting via
custom_instructions.build_persona_block().
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from backend.auth.dependencies import get_current_user
from backend.shared.services import custom_instructions

router = APIRouter(prefix="/memory", tags=["memory"])
_bearer = HTTPBearer(auto_error=True)


class CustomInstructions(BaseModel):
    call_name: str | None = None
    instructions: str | None = None


@router.get("/instructions", response_model=CustomInstructions)
async def get_instructions(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> CustomInstructions:
    row = await custom_instructions.get_instructions(credentials.credentials, str(user.id))
    return CustomInstructions(
        call_name=row.get("call_name"),
        instructions=row.get("instructions"),
    )


@router.put("/instructions", response_model=CustomInstructions)
async def put_instructions(
    body: CustomInstructions,
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    user: Any = Depends(get_current_user),
) -> CustomInstructions:
    row = await custom_instructions.upsert_instructions(
        credentials.credentials,
        str(user.id),
        call_name=body.call_name,
        instructions=body.instructions,
    )
    return CustomInstructions(
        call_name=row.get("call_name"),
        instructions=row.get("instructions"),
    )

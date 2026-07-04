import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Claim(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    paper_id: str = Field(alias="paperId")
    # ArXiv ID enriched from paper.external_ids at extract time (Step ⑤) so the
    # verifier's Case B (ar5iv full-text fetch) can run — without it every claim
    # falls through to Case C (abstract-only, never "Supported").
    arxiv_id: str | None = None
    status: Literal["pending", "supported", "partial", "unsupported", "uncertain"] = "pending"
    # Citation intent from Semantic Scholar snowball metadata (SPEC_1.0.1 §⑦)
    intent: Literal["Supporting", "Contrasting", "Mentioning"] | None = None
    # Verification source used (SPEC_1.0.1 §⑧ 3-tier)
    source: Literal["snippet", "arxiv", "abstract"] | None = None
    # True when only abstract was available — cannot confirm "Supported" (SPEC Case C)
    low_confidence: bool = False
    human_review: bool = False
    snippet: str | None = None  # quote from source text


class ClaimExtractRequest(BaseModel):
    content: str
    theme: str | None = None


class ClaimExtractResponse(BaseModel):
    claims: list[Claim]


class ClaimVerifyRequest(BaseModel):
    claims: list[Claim]


class ClaimVerifyResponse(BaseModel):
    claims: list[Claim]
    supported: int
    partial: int
    unsupported: int
    uncertain: int

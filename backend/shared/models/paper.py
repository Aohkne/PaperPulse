from pydantic import BaseModel, ConfigDict, Field


class Paper(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    paper_id: str = Field(alias="paperId")
    title: str
    abstract: str | None = None
    year: int | None = None
    citation_count: int | None = Field(default=None, alias="citationCount")
    authors: list[str] = []
    url: str | None = None
    open_access_pdf: str | None = Field(default=None, alias="openAccessPdf")
    open_access_pdf_status: str | None = Field(default=None, alias="openAccessPdfStatus")
    external_ids: dict = Field(default_factory=dict, alias="externalIds")
    embedding: list[float] | None = None
    # Snowball metadata (set during ②bis)
    is_influential: bool = Field(default=False, alias="isInfluential")
    intents: list[str] = []
    # Which API this paper came from (SPEC 2.0 §Step ①) — set by the search service
    source: str | None = None
    venue: str | None = None


class PaperSearchRequest(BaseModel):
    query: str
    limit: int = 100


class PaperSearchResponse(BaseModel):
    papers: list[Paper]
    total: int


class EmbedRequest(BaseModel):
    paper_ids: list[str]


class EmbedResponse(BaseModel):
    embedded: int
    stored: int

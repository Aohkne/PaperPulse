from datetime import datetime

from pydantic import BaseModel


class Theme(BaseModel):
    title: str
    description: str
    paper_ids: list[str] = []
    content: str | None = None


class OutlineRequest(BaseModel):
    query: str
    top_k: int = 20


class OutlineResponse(BaseModel):
    query: str
    themes: list[Theme]


class ThemeContentRequest(BaseModel):
    theme: Theme
    top_k: int = 10


class ThemeContentResponse(BaseModel):
    theme: str
    content: str
    paper_ids: list[str]


class LiteratureReview(BaseModel):
    topic: str
    themes: list[Theme]
    full_content: str
    created_at: str = ""

    def model_post_init(self, __context):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

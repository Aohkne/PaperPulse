from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env relative to the project root, regardless of CWD
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "PaperPulse"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:5173"

    # LLM Provider
    provider: Literal["openai", "anthropic", "google", "custom"] = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Embedding
    embedding_model: str = "nv-embed-v1"
    embedding_base_url: str = ""

    # Semantic Scholar
    semantic_scholar_api_key: str = ""

    # OpenAlex (polite pool — no key required, but email improves rate limits)
    openalex_email: str = ""

    # ChromaDB — "embedded" runs in-process (chromadb.PersistentClient, default,
    # no extra setup); "http" talks to a chroma server (e.g. the official
    # `chromadb/chroma` Docker image) via chromadb.HttpClient — lets the backend
    # run natively while only the (heavier-to-install) Chroma server lives in Docker.
    chroma_mode: Literal["embedded", "http"] = "embedded"
    chroma_persist_path: str = "./data/chroma"
    chroma_host: str = "localhost"
    chroma_port: int = 8002

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""  # service_role key — bypasses RLS, used for server-side admin checks

    # Per-role LLM temperatures (SPEC 2.0 §temperature routing)
    intent_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    outline_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    claim_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    verifier_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    export_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # LaTeX output directory (research pipeline v2)
    latex_output_dir: str = "./data/output"

    # MMR (Maximal Marginal Relevance) — SPEC 2.0 §Step ④⑤
    mmr_lambda: float = Field(default=0.5, ge=0.0, le=1.0)
    mmr_prefetch_outline: int = 150   # fetch_k before MMR for Step ④ (outline, k=20)
    mmr_prefetch_theme: int = 50      # fetch_k before MMR for Step ⑤ (per-theme, k=10)

    # Search guardrails — SPEC 2.0 §System Guardrails
    max_sub_queries: int = 6
    max_papers_per_source: int = 200
    max_papers_total: int = 1500
    max_search_calls: int = 15
    min_sources_required: int = 2

    # LangGraph checkpointer (SQLite, persists across server restarts)
    langgraph_checkpoint_db: str = "./data/checkpoints.db"

    # Knowledge Graph guardrails — knowledge-graph_SPEC_2.0.md §System Guardrails
    kg_max_nodes_rendered: int = 500
    kg_max_edges_rendered: int = 3000
    kg_contradicts_cluster_min_size: int = 2

    # ── PDF Agent (pdf-agent_PLAN_2.0.md) ──────────────────────────────────
    pdf_agent_checkpoint_db: str = "./data/pdf_agent_checkpoints.db"
    pdf_agent_output_dir: str = "./data/pdf_agent_output"

    # MinerU (self-host) — see services/mineru_client.py. Falls back to PyMuPDF
    # (services/pdf_parser.py) if unavailable in either mode.
    # "cli"  = subprocess to a local `mineru` binary (needs the package installed
    #          in THIS process's Python env — heavy: torch/paddle/onnxruntime).
    # "http" = call a `mineru-api` server over HTTP (e.g. running in Docker) —
    #          lets the backend run natively without installing MinerU's ML deps.
    mineru_mode: Literal["cli", "http"] = "cli"
    mineru_bin: str = "mineru"
    mineru_tmp_dir: str = "./data/mineru_tmp"
    mineru_device_mode: Literal["cpu", "cuda"] = "cpu"
    mineru_timeout_s: float = 120.0
    mineru_api_url: str = "http://localhost:8001"

    # Per-role LLM temperatures — distinct from research_agent's roles (§2)
    critic_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    explain_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    rewrite_temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    pdf_judge_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # ── Payment (payment_SPEC_2.0.md) ──────────────────────────────────────
    payos_client_id: str = ""
    payos_api_key: str = ""
    payos_checksum_key: str = ""
    frontend_base_url: str = "http://localhost:5173"

    # Guardrails — PDF_AGENT_GUARDRAILS (SPEC §System Guardrails)
    pdf_agent_max_file_size_mb: int = 20
    pdf_agent_max_pages: int = 60
    pdf_agent_max_citations_verify: int = 150
    pdf_agent_max_sections_critic: int = 20
    pdf_agent_citation_lookup_timeout_s: float = 10.0
    pdf_agent_link_check_timeout_s: float = 5.0
    pdf_agent_anchor_context_chars: int = 32
    pdf_agent_match_threshold_high: float = 0.85
    pdf_agent_match_threshold_low: float = 0.55
    pdf_agent_llm_call_timeout_s: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm(temperature: float | None = None, streaming: bool = True):
    """Return a configured LangChain ChatOpenAI instance for the current provider."""
    from langchain_openai import ChatOpenAI

    s = get_settings()
    effective_temp = temperature if temperature is not None else s.llm_temperature
    kwargs: dict = {
        "model": s.llm_model,
        "api_key": s.llm_api_key,
        "temperature": effective_temp,
        "streaming": streaming,
    }
    if s.llm_base_url:
        kwargs["base_url"] = s.llm_base_url
    return ChatOpenAI(**kwargs)

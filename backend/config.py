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

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_key: str = ""  # service_role key — bypasses RLS, used for server-side admin checks

    # Supabase Postgres — pooled connection string (Supavisor, transaction
    # mode, port 6543). Used directly by psycopg for: (1) the LangGraph
    # checkpointers (research_agent/graph/graph.py, pdf_agent/graph/graph.py)
    # — that library talks raw SQL, not PostgREST, so it can't go through
    # supabase_url. paper_embeddings (pgvector) still go through
    # PostgREST/RPC via supabase_url + supabase_service_key, matching the
    # admin.py convention (see WORKLOG.md re: supabase-py + sb_publishable_ keys).
    supabase_db_url: str = ""

    # Per-role LLM temperatures (SPEC 2.0 §temperature routing)
    intent_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    claim_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    verifier_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    export_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # LaTeX output directory (research pipeline v2)
    latex_output_dir: str = "./data/output"

    # Search guardrails — SPEC 2.0 §System Guardrails. No max_search_calls cap:
    # search is I/O-bound (asyncio.gather), so the full sub_query×source fan-out
    # runs concurrently without a meaningful slowdown.
    max_sub_queries: int = 6
    max_papers_per_source: int = 200
    max_papers_total: int = 1500
    min_sources_required: int = 2
    # arXiv is no longer a research search source, but arxiv_search.py still
    # serves the PDF Agent's single-paper citation lookup — keep its worker pool.
    arxiv_search_max_workers: int = 2

    # Relevance filter — Step ①bis (extension). Hybrid BM25 ∥ NIM-semantic → RRF
    # → keep top-K relevant papers before clustering. Drops off-topic papers a
    # broad multi-source search pulls in.
    relevance_top_k: int = 300
    relevance_min: int = 20  # floor: fewer survivors → low_relevance flag
    relevance_rrf_k: int = 60  # RRF constant (Cormack et al. 2009)

    # Clustering guardrails — Step ③ (AutoSurvey, arXiv:2406.10252). Replaces MMR
    # outline + per-theme hybrid search with k-means over SPECTER v2 vectors.
    cluster_k_min: int = 3
    cluster_k_max: int = 10
    cluster_min_papers: int = 3  # clusters smaller than this are discarded as outliers
    cluster_max_papers_per_theme: int = 15  # cap papers/cluster before LLM naming (context rot)
    cluster_temperature: float = Field(default=0.7, ge=0.0, le=2.0)  # LLM cluster naming

    # Research Agent LLM call timeout — same protection pdf_agent already has
    # via ainvoke_with_timeout() (optimize_Plan.html §2.3); without it an SSE
    # stream can hang indefinitely if the LLM provider stalls.
    research_agent_llm_call_timeout_s: float = 60.0

    # Knowledge Graph guardrails — knowledge-graph_SPEC_2.0.md §System Guardrails
    kg_max_nodes_rendered: int = 500
    kg_max_edges_rendered: int = 3000
    kg_contradicts_cluster_min_size: int = 2

    # ── PDF Agent (pdf-agent_PLAN_2.0.md) ──────────────────────────────────
    pdf_agent_output_dir: str = "./data/pdf_agent_output"
    pdf_parser_max_workers: int = 2  # ThreadPoolExecutor size — tune to Cloud Run instance's CPU allocation
    pdf_agent_upload_concurrency: int = (
        4  # max simultaneous /upload requests before returning 429 (optimize_Plan.html §2.2)
    )

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
    pdf_agent_citation_lookup_timeout_s: float = 15.0
    # Max citations verified concurrently. Kept small because every lookup shares
    # the global 1 req/s Semantic Scholar rate limiter — firing all citations at
    # once makes each wait far longer than the per-call timeout and ALL time out.
    pdf_agent_citation_verify_concurrency: int = 4
    pdf_agent_link_check_timeout_s: float = 5.0
    pdf_agent_anchor_context_chars: int = 32
    pdf_agent_match_threshold_high: float = 0.85
    pdf_agent_match_threshold_low: float = 0.55
    pdf_agent_llm_call_timeout_s: float = 30.0

    # Topic monitoring guardrails (TIP-TM-001)
    max_auto_topics_per_user: int = 3

    topic_extraction_max_query_length: int = 200
    topic_extraction_min_alnum_chars: int = 3
    topic_monitor_max_papers_per_topic_per_run: int = 50
    topic_monitor_cooldown_hours: int = 24
    topic_monitor_in_app_threshold: float = 0.72

    # ?????? Monitoring (optimize_Plan.html ??5) ???????????????????????????????????????????????????????????????????????????????????????????????????
    sentry_dsn: str = ""  # empty = Sentry disabled (no-op), see main.py lifespan


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm(temperature: float | None = None, streaming: bool = True):
    """Return a configured LangChain ChatOpenAI instance for the current provider.

    stream_usage=True + a TokenMeterCallback make every call report its exact
    token usage into the per-request token meter (token.html §4) — used for
    token-weighted billing without threading a counter through each node.
    """
    from langchain_openai import ChatOpenAI

    s = get_settings()
    effective_temp = temperature if temperature is not None else s.llm_temperature
    kwargs: dict = {
        "model": s.llm_model,
        "api_key": s.llm_api_key,
        "temperature": effective_temp,
        "streaming": streaming,
        "stream_usage": True,
    }
    if s.llm_base_url:
        kwargs["base_url"] = s.llm_base_url

    try:
        from backend.module.payment.services.token_meter import TokenMeterCallback

        if TokenMeterCallback is not None:
            kwargs["callbacks"] = [TokenMeterCallback()]
    except Exception:
        pass  # metering is best-effort — never block LLM construction

    return ChatOpenAI(**kwargs)

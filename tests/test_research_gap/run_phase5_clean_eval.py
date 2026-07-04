from __future__ import annotations

import asyncio
import json
import os
import pathlib
import statistics
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from backend.agent.gap_detection.gap_similarity import cluster_gaps
from backend.agent.gap_detection.orchestrator import cold_start
from backend.agent.gap_detection.schemas import GapItem
from backend.agent.gap_detection.services.unpaywall import _reset_cache_for_tests

ROOT = pathlib.Path(__file__).parent
TOPICS_FILE = ROOT / "phase5_clean_topics.json"
RESULT_JSON = ROOT / "phase5_clean_eval_results.json"
RESULT_MD = ROOT / "phase5_clean_eval_report.md"

QUERY_DELAY_SECONDS = int(os.getenv("P5_A2_QUERY_DELAY", "10"))
QUERY_LIMIT = int(os.getenv("P5_A2_QUERY_LIMIT", "3"))
QUERY_START = int(os.getenv("P5_A2_QUERY_START", "0"))
MODE_FILTER = [m.strip() for m in os.getenv("P5_A2_MODES", "off,on").split(",") if m.strip()]
CONFIGS = {
    "off": {
        "GAP_DIVERSITY_ENABLED": "false",
        "SELF_CONSISTENCY_ENABLED": "false",
        "COUNTER_CRITIQUE_ENABLED": "false",
        "UNPAYWALL_ENABLED": "false",
    },
    "on": {
        "GAP_DIVERSITY_ENABLED": "true",
        "SELF_CONSISTENCY_ENABLED": "true",
        "COUNTER_CRITIQUE_ENABLED": "true",
        "UNPAYWALL_ENABLED": "true",
    },
}
DEFAULT_MAX_PAPERS = os.getenv("P5_A2_MAX_PAPERS", "10")


@dataclass
class EvalTelemetry:
    diversity_calls: list[dict[str, Any]] = field(default_factory=list)
    critique_calls: list[dict[str, Any]] = field(default_factory=list)
    extraction_events: list[dict[str, Any]] = field(default_factory=list)
    unpaywall_requests: list[dict[str, Any]] = field(default_factory=list)
    unpaywall_hits: list[dict[str, Any]] = field(default_factory=list)


def _load_topics() -> list[dict[str, Any]]:
    return json.loads(TOPICS_FILE.read_text(encoding="utf-8"))


def _quality_summary(gaps: list[GapItem]) -> dict[str, Any]:
    if not gaps:
        return {
            "gap_count": 0,
            "mean_total": None,
            "max_total": None,
            "axis_mean": {},
            "totals": [],
        }

    totals = [gap.quality_score for gap in gaps if gap.quality_score is not None]
    axis_names = ["grounding", "novelty", "actionable", "corpus_evidence"]
    axis_mean: dict[str, float | None] = {}
    for axis in axis_names:
        values = [
            gap.quality_breakdown.get(axis)
            for gap in gaps
            if gap.quality_breakdown and gap.quality_breakdown.get(axis) is not None
        ]
        axis_mean[axis] = round(statistics.mean(values), 4) if values else None
    return {
        "gap_count": len(gaps),
        "mean_total": round(statistics.mean(totals), 4) if totals else None,
        "max_total": round(max(totals), 4) if totals else None,
        "axis_mean": axis_mean,
        "totals": [round(v, 4) for v in totals],
    }


async def _duplicate_metric(gaps: list[GapItem]) -> dict[str, Any]:
    if not gaps:
        return {"cluster_count": 0, "duplicate_count": 0, "clusters": []}
    clusters = await cluster_gaps(gaps)
    return {
        "cluster_count": len(clusters),
        "duplicate_count": sum(max(0, len(cluster) - 1) for cluster in clusters),
        "clusters": clusters,
    }


async def _run_one(topic_entry: dict[str, Any], mode: str) -> dict[str, Any]:
    telemetry = EvalTelemetry()
    _reset_cache_for_tests()

    import backend.agent.gap_detection.nodes.extractor as extractor_mod
    import backend.agent.gap_detection.nodes.synthesizer as synth_mod

    original_analyze = synth_mod.analyze_gaps_llm
    original_critique = synth_mod.critique_top_gaps
    original_extract = extractor_mod.extract_from_text
    original_get_oa = extractor_mod.get_oa_pdf_url

    async def traced_analyze(*args, **kwargs):
        result = await original_analyze(*args, **kwargs)
        telemetry.diversity_calls.append(
            {
                "groups": result.get("groups", []),
                "intent_aligned": result.get("intent_aligned", {}),
            }
        )
        return result

    async def traced_critique(*args, **kwargs):
        result = await original_critique(*args, **kwargs)
        telemetry.critique_calls.append(
            {
                "verdicts": result,
                "removed": sum(1 for verdict in result.values() if bool(verdict.get("already_solved", False))),
                "moderated": sum(
                    1
                    for verdict in result.values()
                    if str(verdict.get("level", "none")) in {"moderate", "strong"}
                    and not bool(verdict.get("already_solved", False))
                ),
            }
        )
        return result

    async def traced_extract(*args, **kwargs):
        result = await original_extract(*args, **kwargs)
        if result is not None:
            telemetry.extraction_events.append(
                {
                    "paper_id": result.paper_ref.paper_id,
                    "doi": result.paper_ref.doi,
                    "source": result.extraction_source,
                    "pdf_url": result.pdf_url,
                }
            )
        return result

    async def traced_get_oa(doi: str, email: str):
        url = await original_get_oa(doi, email)
        event = {"doi": doi, "email": email, "oa_url": url}
        telemetry.unpaywall_requests.append(event)
        if url:
            telemetry.unpaywall_hits.append(event)
        return url

    env_updates = {
        **CONFIGS[mode],
        "MAX_PAPERS_FOR_GAP": DEFAULT_MAX_PAPERS,
    }
    previous_env = {key: os.environ.get(key) for key in env_updates}
    for key, value in env_updates.items():
        os.environ[key] = value

    started = time.perf_counter()
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(synth_mod, "analyze_gaps_llm", side_effect=traced_analyze))
            stack.enter_context(patch.object(synth_mod, "critique_top_gaps", side_effect=traced_critique))
            stack.enter_context(patch.object(extractor_mod, "extract_from_text", side_effect=traced_extract))
            stack.enter_context(patch.object(extractor_mod, "get_oa_pdf_url", side_effect=traced_get_oa))
            report = await cold_start(topic_entry["topic"])
    finally:
        for key, old_value in previous_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value

    elapsed = round(time.perf_counter() - started, 2)
    gaps = report.gaps
    quality = _quality_summary(gaps)
    duplicates = await _duplicate_metric(gaps)
    low_confidence_count = sum(1 for gap in gaps if gap.low_confidence)
    extraction_sources = {
        "fulltext": sum(1 for item in telemetry.extraction_events if item["source"] == "fulltext"),
        "abstract": sum(1 for item in telemetry.extraction_events if item["source"] == "abstract"),
        "unpaywall_hits": len(telemetry.unpaywall_hits),
    }

    return {
        "topic": topic_entry["topic"],
        "domain": topic_entry.get("domain"),
        "mode": mode,
        "flags": env_updates,
        "runtime_seconds": elapsed,
        "papers_analyzed": report.papers_analyzed,
        "gap_count": len(gaps),
        "quality": quality,
        "duplicates": duplicates,
        "low_confidence_count": low_confidence_count,
        "fulltext_coverage": extraction_sources,
        "telemetry": {
            "diversity_calls": telemetry.diversity_calls,
            "critique_calls": telemetry.critique_calls,
            "extraction_events": telemetry.extraction_events,
            "unpaywall_requests": telemetry.unpaywall_requests,
            "unpaywall_hits": telemetry.unpaywall_hits,
        },
        "gap_snapshot": [
            {
                "statement": gap.statement,
                "quality_score": gap.quality_score,
                "quality_breakdown": gap.quality_breakdown,
                "low_confidence": gap.low_confidence,
                "supporting_papers": [paper.paper_id for paper in gap.supporting_papers],
            }
            for gap in gaps
        ],
    }


def _format_compare(off: dict[str, Any], on: dict[str, Any]) -> str:
    return (
        f"quality mean {off['quality']['mean_total']} -> {on['quality']['mean_total']} | "
        f"dup {off['duplicates']['duplicate_count']} -> {on['duplicates']['duplicate_count']} | "
        f"fulltext {off['fulltext_coverage']['fulltext']} -> {on['fulltext_coverage']['fulltext']} "
        f"(Unpaywall {off['fulltext_coverage']['unpaywall_hits']} -> {on['fulltext_coverage']['unpaywall_hits']}) | "
        f"low_conf {off['low_confidence_count']} -> {on['low_confidence_count']} | "
        f"runtime {off['runtime_seconds']}s -> {on['runtime_seconds']}s"
    )


def _find_evidence(results: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = {
        "a1r_grouping": None,
        "a3_intent_aligned": None,
        "b1_low_confidence": None,
        "b2_critique": None,
        "c1_unpaywall": None,
    }
    for item in results:
        if item["mode"] != "on":
            continue
        if evidence["a1r_grouping"] is None and item["telemetry"]["diversity_calls"]:
            first = item["telemetry"]["diversity_calls"][0]
            evidence["a1r_grouping"] = {
                "topic": item["topic"],
                "groups": first.get("groups", []),
            }
        if evidence["a3_intent_aligned"] is None:
            for call in item["telemetry"]["diversity_calls"]:
                intent = call.get("intent_aligned", {})
                if any(value is False for value in intent.values()):
                    evidence["a3_intent_aligned"] = {
                        "topic": item["topic"],
                        "intent_aligned": intent,
                    }
                    break
        if evidence["b1_low_confidence"] is None and item["low_confidence_count"] > 0:
            evidence["b1_low_confidence"] = {
                "topic": item["topic"],
                "low_confidence_count": item["low_confidence_count"],
                "gaps": [gap["statement"] for gap in item["gap_snapshot"] if gap["low_confidence"]][:3],
            }
        if evidence["b2_critique"] is None:
            for call in item["telemetry"]["critique_calls"]:
                if call["removed"] > 0 or call["moderated"] > 0:
                    evidence["b2_critique"] = {
                        "topic": item["topic"],
                        "removed": call["removed"],
                        "moderated": call["moderated"],
                        "verdicts": call["verdicts"],
                    }
                    break
        if evidence["c1_unpaywall"] is None and item["telemetry"]["unpaywall_hits"]:
            evidence["c1_unpaywall"] = {
                "topic": item["topic"],
                "hits": item["telemetry"]["unpaywall_hits"][:3],
            }
    return evidence


def _write_markdown(results: list[dict[str, Any]], evidence: dict[str, Any]) -> None:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for item in results:
        grouped.setdefault(item["topic"], {})[item["mode"]] = item

    lines: list[str] = []
    lines.append("# Phase 5 Clean-Run Eval")
    lines.append("")
    lines.append(f"Query delay: {QUERY_DELAY_SECONDS}s")
    lines.append(f"MAX_PAPERS_FOR_GAP via env: {DEFAULT_MAX_PAPERS}")
    lines.append("")
    lines.append("## Query Set")
    for topic in _load_topics():
        lines.append(f"- {topic['topic']} [{topic['domain']}]")
    lines.append("")
    lines.append("## OFF vs ON")
    for topic, modes in grouped.items():
        off = modes.get("off")
        on = modes.get("on")
        if off and on:
            lines.append(f"- {topic}: {_format_compare(off, on)}")
        elif off:
            lines.append(
                f"- {topic}: OFF only | quality mean {off['quality']['mean_total']} | dup {off['duplicates']['duplicate_count']} | fulltext {off['fulltext_coverage']['fulltext']} | low_conf {off['low_confidence_count']} | runtime {off['runtime_seconds']}s"
            )
        elif on:
            lines.append(
                f"- {topic}: ON only | quality mean {on['quality']['mean_total']} | dup {on['duplicates']['duplicate_count']} | fulltext {on['fulltext_coverage']['fulltext']} (Unpaywall {on['fulltext_coverage']['unpaywall_hits']}) | low_conf {on['low_confidence_count']} | runtime {on['runtime_seconds']}s"
            )
    lines.append("")
    lines.append("## Official Quality Ceiling")
    for topic, modes in grouped.items():
        target = modes.get("on") or modes.get("off")
        lines.append(
            f"- {topic}: mean_total={target['quality']['mean_total']}, max_total={target['quality']['max_total']}, axis_mean={target['quality']['axis_mean']}"
        )
    lines.append("")
    lines.append("## End-to-End Evidence")
    for key, value in evidence.items():
        lines.append(f"- {key}: {value}")
    RESULT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checkpoint(results: list[dict[str, Any]]) -> None:
    evidence = _find_evidence(results)
    payload = {
        "query_set": _load_topics()[QUERY_START : QUERY_START + QUERY_LIMIT],
        "max_papers_for_gap": DEFAULT_MAX_PAPERS,
        "query_delay_seconds": QUERY_DELAY_SECONDS,
        "query_limit": QUERY_LIMIT,
        "query_start": QUERY_START,
        "mode_filter": MODE_FILTER,
        "results": results,
        "evidence": evidence,
    }
    RESULT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(results, evidence)


async def main() -> None:
    topics = _load_topics()[QUERY_START : QUERY_START + QUERY_LIMIT]
    results: list[dict[str, Any]] = []
    for topic_index, topic_entry in enumerate(topics):
        for mode in MODE_FILTER:
            print(f"Running {mode.upper()} :: {topic_entry['topic']}")
            results.append(await _run_one(topic_entry, mode))
            _write_checkpoint(results)
        if topic_index < len(topics) - 1:
            print(f"Sleeping {QUERY_DELAY_SECONDS}s before next topic...")
            await asyncio.sleep(QUERY_DELAY_SECONDS)

    evidence = _find_evidence(results)
    payload = {
        "query_set": topics,
        "max_papers_for_gap": DEFAULT_MAX_PAPERS,
        "query_delay_seconds": QUERY_DELAY_SECONDS,
        "query_limit": QUERY_LIMIT,
        "query_start": QUERY_START,
        "mode_filter": MODE_FILTER,
        "results": results,
        "evidence": evidence,
    }
    RESULT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(results, evidence)
    print(f"Saved JSON: {RESULT_JSON}")
    print(f"Saved Markdown: {RESULT_MD}")


if __name__ == "__main__":
    asyncio.run(main())

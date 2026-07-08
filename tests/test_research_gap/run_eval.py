"""Manual evaluation runner for the research gap detection pipeline.

Usage:
    python tests/test_research_gap/run_eval.py

Reads topics.json, runs cold_start() for each topic, applies structural
checks and LLM judge, then writes a terminal summary and report.html.
"""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
from datetime import datetime

# Load .env.eval nếu có (judge model config, không ảnh hưởng backend)
try:
    from dotenv import load_dotenv

    _env_file = pathlib.Path(__file__).parent.parent.parent / ".env.eval"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
        logging.getLogger(__name__).info("Loaded judge config from %s", _env_file)
except ImportError:
    pass  # python-dotenv not installed — rely on shell env vars

# Set SKIP_LLM_JUDGE=true để chỉ chạy structural checks, bỏ qua LLM judge
import os as _os

from backend.module.gap_detection.orchestrator import cold_start
from backend.module.gap_detection.schemas import GapItem, GapReport
from tests.test_research_gap.structural_checks import check_empty_on_nonsense, check_gap_structural

SKIP_LLM_JUDGE = _os.getenv("SKIP_LLM_JUDGE", "false").lower() == "true"

if not SKIP_LLM_JUDGE:
    from tests.test_research_gap.llm_judge import judge_gap  # type: ignore[assignment]
else:
    judge_gap = None  # type: ignore[assignment]

logging.basicConfig(level=logging.WARNING)

_EVAL_DIR = pathlib.Path(__file__).parent
_TOPICS_FILE = _EVAL_DIR / "topics.json"
_REPORT_FILE = _EVAL_DIR / "report.html"


def _load_topics() -> list[dict]:
    with open(_TOPICS_FILE) as f:
        return json.load(f)


async def _eval_topic(topic_entry: dict) -> dict:
    """Run full evaluation for one topic. Returns structured result dict."""
    topic = topic_entry["topic"]
    expect_empty = topic_entry.get("expect_empty", False)

    print(f"\n⏳ Running: '{topic}'")

    report: GapReport = await cold_start(topic)
    gaps: list[GapItem] = report.gaps

    nonsense_check = check_empty_on_nonsense(gaps, expect_empty)

    gap_results = []
    for i, gap in enumerate(gaps):
        print(f"   Gap {i + 1}/{len(gaps)}: structural...", end=" ", flush=True)
        structural = await check_gap_structural(gap)
        structural_passed = all(r["passed"] for r in structural)
        print("✅" if structural_passed else "❌")

        judge_result = None
        if structural_passed and not expect_empty and not SKIP_LLM_JUDGE:
            print(f"   Gap {i + 1}/{len(gaps)}: LLM judge...", end=" ", flush=True)
            judge_result = await judge_gap(gap)
            print("⚠️  FLAGGED" if judge_result["flagged"] else "✅")

        gap_results.append(
            {
                "statement": gap.statement[:120] + ("..." if len(gap.statement) > 120 else ""),
                "structural": structural,
                "structural_passed": structural_passed,
                "judge": judge_result,
            }
        )

    return {
        "topic": topic,
        "domain": topic_entry.get("domain", ""),
        "expect_empty": expect_empty,
        "papers_analyzed": report.papers_analyzed,
        "gap_count": len(gaps),
        "nonsense_check": nonsense_check,
        "gaps": gap_results,
    }


def _print_report(results: list[dict]) -> tuple[int, int]:
    """Print terminal report. Returns (total_gaps, total_flagged)."""
    total_gaps = 0
    total_flagged = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'=' * 60}")
    print(f"EVAL REPORT — {now}")
    print("=" * 60)

    for res in results:
        print(f'\n📌 Topic: "{res["topic"]}" [{res["domain"]}]')
        print(f"   Papers analyzed: {res['papers_analyzed']} | Gaps: {res['gap_count']}")

        if res["expect_empty"]:
            nc = res["nonsense_check"]
            print(f"   Nonsense check: {'✅' if nc['passed'] else '❌'} — {nc['detail']}")

        for i, gr in enumerate(res["gaps"]):
            total_gaps += 1
            judge = gr["judge"]
            flagged = (not gr["structural_passed"]) or (judge and judge["flagged"])
            if flagged:
                total_flagged += 1

            if not gr["structural_passed"]:
                status = "❌ STRUCTURAL FAIL"
            elif judge and judge["flagged"]:
                status = "⚠️  FLAGGED"
            else:
                status = "✅ PASS"

            print(f"\n   Gap {i + 1}: {status}")
            print(f"   {gr['statement']}")

            for r in gr["structural"]:
                if not r["passed"]:
                    print(f"     ✗ {r['check']}: {r['detail']}")

            if judge:
                avg = (
                    f"avg  G={judge['grounded']} S={judge['specific']} "
                    f"N={judge['non_trivial']} A={judge['method_actionable']}"
                )
                print(f"   Scores: {avg}")
                if judge.get("judges"):
                    c = judge["judges"]["claude"]
                    d = judge["judges"]["deepseek"]
                    print(
                        f"     Claude:   G={c['grounded']} S={c['specific']} N={c['non_trivial']} A={c['method_actionable']}"
                    )
                    print(
                        f"     DeepSeek: G={d['grounded']} S={d['specific']} N={d['non_trivial']} A={d['method_actionable']}"
                    )
                if judge.get("disagreements"):
                    print(f"   ⚡ Disagree on: {', '.join(judge['disagreements'])}")
                if judge.get("flag"):
                    print(f"   Judge note: {judge['flag']}")
                if judge.get("error"):
                    print(f"   ⚠️  Parse error: {judge['error']}")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {total_flagged} flagged / {total_gaps} total gaps.")
    print("=" * 60)
    return total_gaps, total_flagged


def _write_html(results: list[dict], total_gaps: int, total_flagged: int) -> None:
    """Write a minimal HTML report to tests/eval/report.html."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = ""
    for res in results:
        for i, gr in enumerate(res["gaps"]):
            judge = gr["judge"]
            flagged = (not gr["structural_passed"]) or (judge and judge["flagged"])
            bg = "#fff3cd" if flagged else "#d4edda"
            scores_avg = ""
            scores_detail = ""
            if judge and "error" not in judge:
                scores_avg = (
                    f"G={judge['grounded']} S={judge['specific']} "
                    f"N={judge['non_trivial']} A={judge['method_actionable']}"
                )
                if judge.get("judges"):
                    c = judge["judges"]["claude"]
                    d = judge["judges"]["deepseek"]
                    scores_detail = (
                        f"<br><small>Claude: G={c['grounded']} S={c['specific']} N={c['non_trivial']} A={c['method_actionable']}</small>"
                        f"<br><small>DeepSeek: G={d['grounded']} S={d['specific']} N={d['non_trivial']} A={d['method_actionable']}</small>"
                    )
                    if judge.get("disagreements"):
                        scores_detail += (
                            f"<br><small style='color:orange'>⚡ disagree: {', '.join(judge['disagreements'])}</small>"
                        )
            rows += (
                f"<tr style='background:{bg}'>"
                f"<td>{res['topic'][:50]}</td>"
                f"<td>{i + 1}</td>"
                f"<td>{'❌' if not gr['structural_passed'] else '✅'}</td>"
                f"<td>{scores_avg}{scores_detail}</td>"
                f"<td>{'⚠️' if (judge and judge['flagged']) else ('✅' if judge else '—')}</td>"
                f"<td>{gr['statement'][:100]}</td>"
                f"</tr>\n"
            )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Gap Eval Report</title>
<style>
  body {{ font-family: sans-serif; padding: 20px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
  th {{ background: #f5f5f5; }}
</style>
</head><body>
<h1>Research Gap Eval Report</h1>
<p>Generated: {now} | Total gaps: {total_gaps} | Flagged for review: {total_flagged}</p>
<table>
<tr><th>Topic</th><th>#</th><th>Structural</th><th>Scores (G/S/N/A)</th><th>Flagged</th><th>Statement</th></tr>
{rows}
</table>
<p style="color:#888;font-size:12px">
  G=Grounded, S=Specific, N=Non-trivial, A=Actionable method. Avg score 1-5, flagged if avg ≤ 2.5 or disagree ≥ 2. ⚡ = judges disagree.
</p>
</body></html>"""

    _REPORT_FILE.write_text(html, encoding="utf-8")
    print(f"\n📄 Report saved: {_REPORT_FILE}")


_TOPIC_DELAY_SECONDS = 45  # nghỉ giữa các topics để tránh arXiv/S2 rate limit


async def main() -> None:
    topics = _load_topics()
    results = []
    for i, entry in enumerate(topics):
        results.append(await _eval_topic(entry))
        if i < len(topics) - 1:
            print(f"\n⏸  Chờ {_TOPIC_DELAY_SECONDS}s trước topic tiếp theo (tránh rate limit)...")
            await asyncio.sleep(_TOPIC_DELAY_SECONDS)
    total_gaps, total_flagged = _print_report(results)
    _write_html(results, total_gaps, total_flagged)


if __name__ == "__main__":
    asyncio.run(main())

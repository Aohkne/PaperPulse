"""Gap Detection SubGraph assembly (TIP-G06).

Wires the seven Phase-1→4 nodes into a single linear LangGraph, following
the project's documented LangGraph pattern
(``docs/guide/langgraph/nodes-and-edges.md``): ``StateGraph`` → ``add_node``
→ ``set_entry_point`` → ``add_edge`` → ``compile``.

Linear sequence (easy → hard, then verify → synthesize):

    extractor → topical_detector → method_detector → contradiction_detector
        → verifier → counter_search → synthesizer → END

Phase 0 (PaperCheck) is intentionally NOT included here — it will be added
ahead of ``extractor`` in TIP-G07.

NOTE: TIP-G06 referenced ``chat_graph.py`` as the pattern source, but no
such module exists; the existing chat agent (``backend/agent/chat.py``) is
a plain function, not a graph.  The documented LangGraph guide was used
instead.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.module.gap_detection.nodes.contradiction_detector import contradiction_detector_node
from backend.module.gap_detection.nodes.counter_search import counter_search_node
from backend.module.gap_detection.nodes.extractor import extractor_node
from backend.module.gap_detection.nodes.method_detector import method_detector_node
from backend.module.gap_detection.nodes.synthesizer import synthesizer_node
from backend.module.gap_detection.nodes.topical_detector import topical_detector_node
from backend.module.gap_detection.nodes.verifier import verifier_node
from backend.module.gap_detection.schemas import GapDetectionState, GapQuery, GapReport, PaperRef

# Linear node order — the single source of truth for both wiring and tests.
_NODE_SEQUENCE: list[tuple[str, object]] = [
    ("extractor", extractor_node),
    ("topical_detector", topical_detector_node),
    ("method_detector", method_detector_node),
    ("contradiction_detector", contradiction_detector_node),
    ("verifier", verifier_node),
    ("counter_search", counter_search_node),
    ("synthesizer", synthesizer_node),
]


def build_gap_detection_graph() -> CompiledStateGraph:
    """Build and compile the linear gap-detection subgraph.

    Returns a compiled LangGraph with the seven nodes wired in sequence,
    entry point ``extractor`` and final edge into ``END``.
    """
    graph = StateGraph(GapDetectionState)

    # 1. Add nodes.
    for name, node in _NODE_SEQUENCE:
        graph.add_node(name, node)

    # 2. Entry point.
    graph.set_entry_point(_NODE_SEQUENCE[0][0])

    # 3. Linear edges between consecutive nodes, last → END.
    for (src, _), (dst, _) in zip(_NODE_SEQUENCE, _NODE_SEQUENCE[1:]):
        graph.add_edge(src, dst)
    graph.add_edge(_NODE_SEQUENCE[-1][0], END)

    return graph.compile()


async def run_gap_detection(
    session_papers: list[PaperRef],
    *,
    gap_query: GapQuery | None = None,
    density_signal: dict | None = None,
    coverage: float | None = None,
) -> GapReport:
    """Run the full gap-detection pipeline over *session_papers*.

    Convenience entry point for callers (and TIP-G07): seeds the state with
    the session papers, invokes the compiled graph, and returns the
    synthesized ``GapReport``.

    ``gap_query`` is optional; when provided (from cold_start Stage A) it is
    seeded into state so the synthesizer can apply intent re-scoring (TIP-402).

    ``density_signal`` and ``coverage`` are optional; when provided (from
    Stage D-c/D-b) they are seeded into state so co-occurrence (TIP-406) can
    read which cells are trustworthy.
    """
    graph = build_gap_detection_graph()
    initial_state: GapDetectionState = {"session_papers": session_papers}
    if gap_query is not None:
        initial_state["gap_query"] = gap_query
    if density_signal is not None:
        initial_state["density_signal"] = density_signal  # type: ignore[typeddict-unknown-key]
    if coverage is not None:
        initial_state["coverage_estimate"] = coverage  # type: ignore[typeddict-unknown-key]
    final_state = await graph.ainvoke(initial_state)
    return final_state["final_report"]

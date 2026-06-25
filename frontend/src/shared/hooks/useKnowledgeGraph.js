import { useEffect, useState } from 'react';
import Graph from 'graphology';
import { API_ENDPOINTS } from '@/shared/constant/endpoints';

/**
 * useKnowledgeGraph — fetches the Step ⑨bis knowledge graph for a session
 * and converts the backend's node_link JSON into a Graphology instance for
 * @react-sigma/core to render.
 *
 * Backend: GET /api/research/graph?thread_id=... (404 until build_graph runs).
 */
export function useKnowledgeGraph(threadId) {
  const [graph, setGraph] = useState(null);
  const [raw, setRaw] = useState(null);   // {nodes, edges, stats} — for sidebars/stat bars
  const [loading, setLoading] = useState(Boolean(threadId));
  const [error, setError] = useState(null);

  // Reset state the moment threadId changes — adjusted during render instead
  // of inside the effect (React docs: "You Might Not Need an Effect").
  const [prevThreadId, setPrevThreadId] = useState(threadId);
  if (threadId !== prevThreadId) {
    setPrevThreadId(threadId);
    if (threadId) {
      setLoading(true);
      setError(null);
    }
  }

  useEffect(() => {
    if (!threadId) return;
    let cancelled = false;

    fetch(`${API_ENDPOINTS.RESEARCH.GRAPH}?thread_id=${encodeURIComponent(threadId)}`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail ?? `HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        setRaw(data);
        setGraph(buildGraphology(data));
      })
      .catch((err) => {
        if (!cancelled) setError(String(err?.message ?? err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [threadId]);

  return { graph, raw, loading, error };
}

// knowledge-graph_SPEC_2.0.md §Bảng màu — topic=amber (not red, to avoid
// reading as "contradicts"), theme=neutral gray, paper=blue, claim=purple.
const TYPE_COLOR = {
  topic: '#d97706',
  theme: '#94a3b8',
  paper: '#4f86c6',
  claim: '#8040e8',
};

const EDGE_COLOR = {
  covers: '#e2ddc8',
  cites: '#cbd5e1',
  belongs_to: '#d4c9a8',
  evidenced_by: '#cbd5e1',
  supports: '#16a34a',
  contradicts: '#dc2626',
  mentions: '#9BAD5A',
};

function buildGraphology(data) {
  const graph = new Graph({ multi: true, type: 'directed' });

  for (const node of data.nodes || []) {
    if (graph.hasNode(node.id)) continue;
    const isClaim = node.type === 'claim';
    const isPaper = node.type === 'paper';
    const isTopic = node.type === 'topic';
    // `type` is reserved by Sigma to pick a node renderer program — store our
    // own topic/theme/paper/claim layer under `kind` instead, or nodes don't render.
    const { type, ...rest } = node;
    graph.addNode(node.id, {
      ...rest,
      kind: type,
      label: node.label,
      color: TYPE_COLOR[type] || '#888',
      size: isTopic
        ? 11
        : isPaper
          ? 3 + Math.min(12, Math.log2((node.citation_count || 0) + 1))
          : isClaim
            ? 3 + (node.confidence || 0) * 6
            : 6,
    });
  }

  for (const edge of data.edges || []) {
    if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) continue;
    // Same reservation applies to edges (line/arrow/curve renderer programs).
    const { type, ...rest } = edge;
    graph.addEdge(edge.source, edge.target, {
      ...rest,
      kind: type,
      color: EDGE_COLOR[type] || '#ccc',
      size: edge.is_influential ? 2 : 1,
    });
  }

  return graph;
}

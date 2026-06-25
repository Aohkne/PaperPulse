import { useEffect, useMemo, useRef, useState } from 'react';
import {
  SigmaContainer, useLoadGraph, useSigma, useRegisterEvents,
  ControlsContainer, ZoomControl, FullScreenControl,
} from '@react-sigma/core';
import { Icon } from '@iconify/react';
import '@react-sigma/core/lib/style.css';
import { useKnowledgeGraph } from '@/shared/hooks/useKnowledgeGraph';
import { computeRadialLayout } from '@/shared/utils/radialLayout';
import { springBackToBase } from '@/shared/utils/springBack';
import NodeDetailCard from './NodeDetailCard';

// ── Loads the graph + applies the static radial "solar system" layout ──────
// (knowledge-graph_SPEC_2.0.md §Frontend "Layout: hệ mặt trời tĩnh, KHÔNG tự
// quay" — deliberately NOT a force-directed simulation, so Topic stays at
// the center and Theme/Paper/Claim sit in deterministic concentric rings.)
const GraphLoader = ({ graph }) => {
  const loadGraph = useLoadGraph();
  useEffect(() => {
    if (!graph) return;
    computeRadialLayout(graph);
    loadGraph(graph);
  }, [graph, loadGraph]);
  return null;
};

// ── Single reducer pass: layer visibility + contradicts-only + click-highlight ──
const GraphFilters = ({ visibleLayers, contradictsOnly, selectedNodeId }) => {
  const sigma = useSigma();
  useEffect(() => {
    const graph = sigma.getGraph();
    let highlighted = null;
    if (selectedNodeId && graph.hasNode(selectedNodeId)) {
      highlighted = new Set([selectedNodeId]);
      graph.forEachNeighbor(selectedNodeId, (n) => highlighted.add(n));
    }

    sigma.setSetting('nodeReducer', (node, data) => {
      if (!visibleLayers.has(data.kind)) return { ...data, hidden: true };
      if (highlighted && !highlighted.has(node)) {
        return { ...data, color: '#e5e1d3', zIndex: 0 };
      }
      return data;
    });

    sigma.setSetting('edgeReducer', (edge, data) => {
      const graph2 = sigma.getGraph();
      const src = graph2.source(edge), tgt = graph2.target(edge);
      const srcKind = graph2.getNodeAttribute(src, 'kind');
      const tgtKind = graph2.getNodeAttribute(tgt, 'kind');
      if (!visibleLayers.has(srcKind) || !visibleLayers.has(tgtKind)) return { ...data, hidden: true };
      if (contradictsOnly && data.kind !== 'contradicts') return { ...data, hidden: true };
      if (highlighted && !(highlighted.has(src) && highlighted.has(tgt))) {
        return { ...data, color: '#ece8da' };
      }
      return data;
    });

    sigma.refresh();
  }, [sigma, visibleLayers, contradictsOnly, selectedNodeId]);
  return null;
};

// ── Click node → select (opens card); click empty stage → deselect ──────────
const GraphClickEvents = ({ onNodeClick, onStageClick }) => {
  const registerEvents = useRegisterEvents();
  useEffect(() => {
    registerEvents({
      clickNode: (e) => onNodeClick?.(e.node),
      clickStage: () => onStageClick?.(),
    });
  }, [registerEvents, onNodeClick, onStageClick]);
  return null;
};

// ── Drag a node, release → spring back to its radial "home" position ───────
// Standard Sigma.js drag-node pattern (downNode/mousemovebody/mouseup).
const GraphDragHandler = () => {
  const sigma = useSigma();
  const registerEvents = useRegisterEvents();
  const draggedNode = useRef(null);
  const isDragging = useRef(false);

  useEffect(() => {
    registerEvents({
      downNode: (e) => {
        isDragging.current = true;
        draggedNode.current = e.node;
      },
      mousemovebody: (e) => {
        if (!isDragging.current || !draggedNode.current) return;
        const pos = sigma.viewportToGraph(e);
        const graph = sigma.getGraph();
        graph.setNodeAttribute(draggedNode.current, 'x', pos.x);
        graph.setNodeAttribute(draggedNode.current, 'y', pos.y);
        e.preventSigmaDefault();
        e.original.preventDefault();
        e.original.stopPropagation();
      },
      mouseup: () => {
        if (draggedNode.current) {
          springBackToBase(sigma.getGraph(), draggedNode.current, sigma);
        }
        isDragging.current = false;
        draggedNode.current = null;
      },
      mousedown: () => {
        if (!sigma.getCustomBBox()) sigma.setCustomBBox(sigma.getBBox());
      },
    });
  }, [registerEvents, sigma]);

  return null;
};

// ── Optional "solar system" rotation — off by default (WCAG 2.3.3/2.2.2) ───
const GraphMotion = ({ enabled, onForceDisable }) => {
  const sigma = useSigma();
  const rafRef = useRef(null);
  const angleRef = useRef(0);

  useEffect(() => {
    if (!enabled) return undefined;
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      onForceDisable?.();
      return undefined;
    }

    const graph = sigma.getGraph();
    const tick = () => {
      angleRef.current += 0.002;
      graph.forEachNode((node, attrs) => {
        if (attrs.kind === 'topic') return;
        const bx = attrs.baseX ?? attrs.x;
        const by = attrs.baseY ?? attrs.y;
        const r = Math.sqrt(bx * bx + by * by);
        const angle = Math.atan2(by, bx) + angleRef.current;
        graph.setNodeAttribute(node, 'x', r * Math.cos(angle));
        graph.setNodeAttribute(node, 'y', r * Math.sin(angle));
      });
      sigma.refresh();
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      // Snap back to the static radial positions when motion stops.
      graph.forEachNode((node, attrs) => {
        if (attrs.baseX !== undefined) graph.setNodeAttribute(node, 'x', attrs.baseX);
        if (attrs.baseY !== undefined) graph.setNodeAttribute(node, 'y', attrs.baseY);
      });
      sigma.refresh();
    };
  }, [enabled, sigma, onForceDisable]);

  return null;
};

const LayerToggle = ({ label, color, active, onToggle, count }) => (
  <button
    onClick={onToggle}
    style={{
      display: 'flex', alignItems: 'center', gap: 6,
      padding: '4px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
      border: `1px solid ${active ? color : 'var(--color-paper-light)'}`,
      background: active ? `${color}1a` : 'transparent',
      color: active ? color : 'var(--color-paper-light)',
      cursor: 'pointer',
    }}
  >
    <span style={{ width: 8, height: 8, borderRadius: '50%', background: active ? color : 'var(--color-paper-light)' }} />
    {label} {typeof count === 'number' ? `(${count})` : ''}
  </button>
);

/**
 * KnowledgeGraphViewer — Step ⑨bis (knowledge-graph_SPEC_2.0.md v1.1).
 *
 * Props:
 *   threadId  string — fetches GET /api/research/graph?thread_id=...
 */
const KnowledgeGraphViewer = ({ threadId }) => {
  const { graph, raw, loading, error } = useKnowledgeGraph(threadId);
  const [visibleLayers, setVisibleLayers] = useState(new Set(['topic', 'theme', 'paper', 'claim']));
  const [contradictsOnly, setContradictsOnly] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [motionEnabled, setMotionEnabled] = useState(false);

  const toggleLayer = (type) =>
    setVisibleLayers((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type); else next.add(type);
      return next;
    });

  const selectedNode = useMemo(
    () => raw?.nodes.find((n) => n.id === selectedNodeId) ?? null,
    [raw, selectedNodeId]
  );

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 20, fontSize: 13, color: 'var(--color-paper-mid)' }}>
        <Icon icon="mdi:loading" className="animate-spin" />
        Loading knowledge graph…
      </div>
    );
  }
  if (error) {
    return (
      <div style={{ padding: 20, fontSize: 13, color: '#dc2626' }}>
        <Icon icon="mdi:alert-circle-outline" style={{ marginRight: 6 }} />
        {error}
      </div>
    );
  }
  if (!graph) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Controls */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <LayerToggle label="Topic" color="#d97706" active={visibleLayers.has('topic')} onToggle={() => toggleLayer('topic')} count={raw?.nodes.filter((n) => n.type === 'topic').length} />
        <LayerToggle label="Theme" color="#94a3b8" active={visibleLayers.has('theme')} onToggle={() => toggleLayer('theme')} count={raw?.stats?.themes} />
        <LayerToggle label="Paper" color="#4f86c6" active={visibleLayers.has('paper')} onToggle={() => toggleLayer('paper')} count={raw?.stats?.papers} />
        <LayerToggle label="Claim" color="#8040e8" active={visibleLayers.has('claim')} onToggle={() => toggleLayer('claim')} count={raw?.stats?.claims} />
        <div style={{ width: 1, height: 18, background: 'var(--color-paper-surface)' }} />
        <button
          onClick={() => setContradictsOnly((v) => !v)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
            border: `1px solid ${contradictsOnly ? '#dc2626' : 'var(--color-paper-light)'}`,
            background: contradictsOnly ? 'rgba(220,38,38,0.1)' : 'transparent',
            color: contradictsOnly ? '#dc2626' : 'var(--color-paper-light)',
            cursor: 'pointer',
          }}
        >
          <Icon icon="mdi:sword-cross" style={{ fontSize: 13 }} />
          Contradicts only ({raw?.stats?.contradicts_edges ?? 0})
        </button>
        <button
          onClick={() => setMotionEnabled((v) => !v)}
          title={motionEnabled ? 'Pause rotation' : 'Enable slow rotation (off by default for accessibility)'}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '4px 10px', borderRadius: 20, fontSize: 12, fontWeight: 600,
            border: `1px solid ${motionEnabled ? 'var(--color-brand-500)' : 'var(--color-paper-light)'}`,
            background: motionEnabled ? 'var(--color-brand-50)' : 'transparent',
            color: motionEnabled ? 'var(--color-brand-600)' : 'var(--color-paper-light)',
            cursor: 'pointer',
          }}
        >
          <Icon icon={motionEnabled ? 'mdi:pause' : 'mdi:play'} style={{ fontSize: 13 }} />
          {motionEnabled ? 'Pause rotation' : 'Motion'}
        </button>
      </div>

      {/* Graph canvas */}
      <div style={{ position: 'relative', height: 480, border: '1px solid var(--color-paper-surface)', borderRadius: 8, overflow: 'hidden' }}>
        <SigmaContainer
          settings={{ renderLabels: false }}
          style={{ height: '100%', width: '100%', background: 'var(--color-paper-bg)' }}
        >
          <GraphLoader graph={graph} />
          <GraphFilters visibleLayers={visibleLayers} contradictsOnly={contradictsOnly} selectedNodeId={selectedNodeId} />
          <GraphClickEvents
            onNodeClick={(id) => setSelectedNodeId((prev) => (prev === id ? null : id))}
            onStageClick={() => setSelectedNodeId(null)}
          />
          <GraphDragHandler />
          <GraphMotion enabled={motionEnabled} onForceDisable={() => setMotionEnabled(false)} />
          <ControlsContainer position="bottom-right">
            <ZoomControl />
            <FullScreenControl />
          </ControlsContainer>
        </SigmaContainer>
      </div>

      {/* Node detail card — sits below the canvas instead of covering it */}
      {selectedNode && (
        <NodeDetailCard
          node={selectedNode}
          nodeId={selectedNodeId}
          raw={raw}
          stats={raw?.stats}
          onClose={() => setSelectedNodeId(null)}
        />
      )}
    </div>
  );
};

export default KnowledgeGraphViewer;

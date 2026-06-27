import { useEffect, useRef, useState } from 'react';

const NODES = [
  { id: 'p1', label: 'Chen et al. 2023', type: 'paper' },
  { id: 'p2', label: 'Patel & Wong 2024', type: 'paper' },
  { id: 'p3', label: 'Liu et al. 2022', type: 'paper' },
  { id: 'p4', label: 'Kumar 2023', type: 'paper' },
  { id: 'p5', label: 'Zhang et al. 2024', type: 'paper' },
  { id: 'p6', label: 'Obi & Lee 2021', type: 'paper' },
  { id: 'a1', label: 'Chen, W.', type: 'author' },
  { id: 'a2', label: 'Patel, R.', type: 'author' },
  { id: 'a3', label: 'Liu, X.', type: 'author' },
  { id: 't1', label: '3D MRI', type: 'topic' },
  { id: 't2', label: 'ResNet', type: 'topic' },
  { id: 't3', label: 'Segmentation', type: 'topic' },
];

const EDGES = [
  { source: 'p1', target: 't1' },
  { source: 'p1', target: 't2' },
  { source: 'p1', target: 'a1' },
  { source: 'p2', target: 't1' },
  { source: 'p2', target: 't3' },
  { source: 'p2', target: 'a2' },
  { source: 'p3', target: 't2' },
  { source: 'p3', target: 't3' },
  { source: 'p3', target: 'a3' },
  { source: 'p4', target: 't3' },
  { source: 'p4', target: 't1' },
  { source: 'p5', target: 't2' },
  { source: 'p5', target: 'a2' },
  { source: 'p6', target: 't3' },
  { source: 'p1', target: 'p2' },
  { source: 'p3', target: 'p5' },
];

const REPULSION = 800;
const SPRING_K = 0.05;
const REST_LEN = 80;
const CENTER_K = 0.01;
const DAMPING = 0.85;
const MAX_TICKS = 200;

const NODE_STYLES = {
  paper:  { r: 18, fill: '#657733', labelColor: '#FBF2DA', fontSize: 10, fontWeight: 400 },
  author: { r: 13, fill: '#EDE8D4', stroke: '#657733', labelColor: '#657733', fontSize: 10, fontWeight: 400 },
  topic:  { r: 22, fill: '#D7E3A4', labelColor: '#291100', fontSize: 11, fontWeight: 500 },
};

const wrapLabel = (label) => {
  if (label.length <= 8) return [label];
  const mid = Math.ceil(label.length / 2);
  let split = label.lastIndexOf(' ', mid);
  if (split <= 0) split = mid;
  const sep = label[split] === ' ';
  return [label.slice(0, split), label.slice(sep ? split + 1 : split)];
};

const LEGEND = [
  { fill: '#657733', stroke: null, label: 'Paper' },
  { fill: '#EDE8D4', stroke: '#657733', label: 'Author' },
  { fill: '#D7E3A4', stroke: null, label: 'Topic' },
];

// Build graph data from real papers prop (max 30 papers to keep perf)
function buildGraphData(papers) {
  if (!papers || papers.length === 0) return { nodes: NODES, edges: EDGES };

  const nodes = [];
  const edges = [];
  const authorSeen = new Set();

  papers.slice(0, 30).forEach((p, i) => {
    const pid = `p_${i}`;
    const shortTitle = p.title ? p.title.slice(0, 18) + (p.title.length > 18 ? '…' : '') : `Paper ${i + 1}`;
    nodes.push({ id: pid, label: shortTitle, type: 'paper' });

    const firstAuthor = p.authors?.[0];
    if (firstAuthor) {
      const aid = `a_${firstAuthor.slice(0, 12)}`;
      if (!authorSeen.has(aid)) {
        authorSeen.add(aid);
        nodes.push({ id: aid, label: firstAuthor.split(' ').pop() ?? firstAuthor, type: 'author' });
      }
      edges.push({ source: pid, target: aid });
    }

    // Link papers that share first author
    papers.slice(0, i).forEach((prev, j) => {
      if (prev.authors?.[0] === firstAuthor) {
        edges.push({ source: pid, target: `p_${j}` });
      }
    });
  });

  return { nodes, edges };
}

export default function KnowledgeGraph({ papers }) {
  const { nodes: graphNodes, edges: graphEdges } = buildGraphData(papers);

  const svgRef = useRef(null);
  const nodesRef = useRef(graphNodes.map((n) => ({ ...n, x: 0, y: 0, vx: 0, vy: 0, r: NODE_STYLES[n.type]?.r ?? 18 })));
  const tickRef = useRef(0);
  const rafRef = useRef(null);

  const [positions, setPositions] = useState(() =>
    Object.fromEntries(graphNodes.map((n) => [n.id, { x: 0, y: 0 }]))
  );
  const [hoveredId, setHoveredId] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      const svg = svgRef.current;
      if (!svg) return;
      const { width, height } = svg.getBoundingClientRect();
      const w = width || 280;
      const h = height || 380;

      nodesRef.current = graphNodes.map((n) => ({ ...n, x: 0, y: 0, vx: 0, vy: 0, r: NODE_STYLES[n.type]?.r ?? 18 }));
      const nodes = nodesRef.current;
      nodes.forEach((n) => {
        n.x = w * 0.15 + Math.random() * w * 0.7;
        n.y = h * 0.15 + Math.random() * h * 0.7;
        n.vx = 0;
        n.vy = 0;
      });

      const nodeMap = new Map(nodes.map((n) => [n.id, n]));
      const cx = w / 2;
      const cy = h / 2;
      tickRef.current = 0;

      const tick = () => {
        if (tickRef.current >= MAX_TICKS) {
          setPositions(Object.fromEntries(nodes.map((n) => [n.id, { x: n.x, y: n.y }])));
          return;
        }
        tickRef.current++;

        // Repulsion between all pairs
        for (let i = 0; i < nodes.length; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const a = nodes[i], b = nodes[j];
            const dx = b.x - a.x, dy = b.y - a.y;
            const d2 = dx * dx + dy * dy || 0.01;
            const d = Math.sqrt(d2);
            const f = REPULSION / d2;
            const fx = (f * dx) / d, fy = (f * dy) / d;
            a.vx -= fx; a.vy -= fy;
            b.vx += fx; b.vy += fy;
          }
        }

        // Spring attraction along edges
        for (const { source, target } of graphEdges) {
          const s = nodeMap.get(source), t = nodeMap.get(target);
          if (!s || !t) continue;
          const dx = t.x - s.x, dy = t.y - s.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
          const f = SPRING_K * (d - REST_LEN);
          const fx = (f * dx) / d, fy = (f * dy) / d;
          s.vx += fx; s.vy += fy;
          t.vx -= fx; t.vy -= fy;
        }

        // Centering + integrate + damp + clamp
        for (const n of nodes) {
          n.vx += CENTER_K * (cx - n.x);
          n.vy += CENTER_K * (cy - n.y);
          n.vx *= DAMPING;
          n.vy *= DAMPING;
          n.x += n.vx;
          n.y += n.vy;
          n.x = Math.max(n.r + 5, Math.min(w - n.r - 5, n.x));
          n.y = Math.max(n.r + 5, Math.min(h - n.r - 5, n.y));
        }

        if (tickRef.current % 3 === 0) {
          setPositions(Object.fromEntries(nodes.map((n) => [n.id, { x: n.x, y: n.y }])));
        }

        rafRef.current = requestAnimationFrame(tick);
      };

      rafRef.current = requestAnimationFrame(tick);
    }, 60);

    return () => {
      clearTimeout(timer);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [papers]);

  const anyVisible = Object.values(positions).some((p) => p.x !== 0 || p.y !== 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* SVG area */}
      <div style={{ width: '100%', height: '100%', overflow: 'hidden', flex: 1 }}>
        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          style={{ display: 'block' }}
        >
          {anyVisible && (
            <>
              {/* Edges */}
              {graphEdges.map((edge, i) => {
                const s = positions[edge.source], t = positions[edge.target];
                if (!s || !t || s.x === 0) return null;
                return (
                  <line
                    key={i}
                    x1={s.x} y1={s.y}
                    x2={t.x} y2={t.y}
                    stroke="#D7E3A4"
                    strokeWidth={1}
                    opacity={0.8}
                  />
                );
              })}

              {/* Nodes */}
              {graphNodes.map((node) => {
                const pos = positions[node.id];
                if (!pos || pos.x === 0) return null;
                const hovered = hoveredId === node.id;
                const selected = selectedId === node.id;
                const style = NODE_STYLES[node.type] ?? NODE_STYLES.paper;
                const r = style.r + (hovered ? 4 : 0);
                const lines = wrapLabel(node.label);

                return (
                  <g
                    key={node.id}
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredId(node.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    onClick={() => setSelectedId(selectedId === node.id ? null : node.id)}
                  >
                    <title>{node.label}</title>

                    {selected && (
                      <circle
                        cx={pos.x} cy={pos.y} r={r + 4}
                        fill="none"
                        stroke="#291100"
                        strokeWidth={2}
                      />
                    )}

                    <circle
                      cx={pos.x} cy={pos.y} r={r}
                      fill={style.fill}
                      stroke={style.stroke ?? 'none'}
                      strokeWidth={style.stroke ? 1 : 0}
                    />

                    <text
                      textAnchor="middle"
                      fill={style.labelColor}
                      fontSize={style.fontSize}
                      fontFamily="Noto Serif, serif"
                      fontWeight={style.fontWeight}
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {lines.map((line, li) => (
                        <tspan
                          key={li}
                          x={pos.x}
                          y={pos.y + (li - (lines.length - 1) / 2) * (style.fontSize * 1.25)}
                        >
                          {line}
                        </tspan>
                      ))}
                    </text>
                  </g>
                );
              })}
            </>
          )}
        </svg>
      </div>

      {/* Legend */}
      <div
        style={{
          display: 'flex',
          gap: '14px',
          padding: '8px 14px',
          borderTop: '1px solid var(--color-paper-surface)',
          flexShrink: 0,
          alignItems: 'center',
        }}
      >
        {LEGEND.map(({ fill, stroke, label }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <svg width="12" height="12">
              <circle cx="6" cy="6" r="5" fill={fill} stroke={stroke ?? 'none'} strokeWidth={stroke ? 1 : 0} />
            </svg>
            <span style={{ fontSize: '12px', color: 'var(--color-paper-light)', fontFamily: "'Noto Serif', serif" }}>
              {label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

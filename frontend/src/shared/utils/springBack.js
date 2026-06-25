/**
 * springBack — tween a dragged node back to its radial "home" position
 * (knowledge-graph_SPEC_2.0.md §Tương tác "Kéo node rồi buông").
 *
 * The graph's static radial layout (radialLayout.js) is the source of
 * truth for where every node belongs — dragging is just a temporary
 * inspection gesture, so on mouseup we always tween back to `baseX`/`baseY`
 * rather than leaving the node wherever it was dropped.
 */

const DURATION_MS = 250;

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

export function springBackToBase(graph, nodeId, sigma) {
  if (!graph.hasNode(nodeId)) return;
  const baseX = graph.getNodeAttribute(nodeId, 'baseX');
  const baseY = graph.getNodeAttribute(nodeId, 'baseY');
  if (baseX === undefined || baseY === undefined) return;

  const startX = graph.getNodeAttribute(nodeId, 'x');
  const startY = graph.getNodeAttribute(nodeId, 'y');
  const start = performance.now();

  function tick() {
    if (!graph.hasNode(nodeId)) return;
    const elapsed = performance.now() - start;
    const t = Math.min(1, elapsed / DURATION_MS);
    const eased = easeOutCubic(t);
    graph.setNodeAttribute(nodeId, 'x', startX + (baseX - startX) * eased);
    graph.setNodeAttribute(nodeId, 'y', startY + (baseY - startY) * eased);
    sigma?.refresh();
    if (t < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

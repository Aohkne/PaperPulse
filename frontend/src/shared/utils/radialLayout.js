/**
 * radialLayout — static "solar system" layout for the Knowledge Graph
 * (knowledge-graph_SPEC_2.0.md §Frontend "Layout: hệ mặt trời tĩnh").
 *
 * Converts the 4-tier tree (Topic → Theme → Paper → Claim) into polar
 * coordinates: angle = position among siblings, radius = depth. Topic sits
 * at the origin so the eye has one fixed point to start from. No external
 * dependency needed — the tree is only 4 levels deep with small fanout.
 *
 * Stores `baseX`/`baseY` separately from the live `x`/`y` so a node dragged
 * away from its position can always be sprung back to where it belongs
 * (see springBack.js).
 */

const RADIUS = { theme: 150, paper: 320, claim: 480 };

export function computeRadialLayout(graph) {
  const topicId = graph.nodes().find((n) => graph.getNodeAttribute(n, 'kind') === 'topic');
  if (topicId) {
    graph.mergeNodeAttributes(topicId, { x: 0, y: 0, baseX: 0, baseY: 0 });
  }

  const themes = graph.filterNodes((_, attrs) => attrs.kind === 'theme');
  const themeAngle = {};

  themes.forEach((themeId, i) => {
    const angle = (2 * Math.PI * i) / Math.max(themes.length, 1);
    themeAngle[themeId] = angle;
    const x = RADIUS.theme * Math.cos(angle);
    const y = RADIUS.theme * Math.sin(angle);
    graph.mergeNodeAttributes(themeId, { x, y, baseX: x, baseY: y });
  });

  // Papers — placed in the angular sector of the (first) theme they belong to.
  // `belongs_to` edges point paper -> theme, so out-neighbors of a paper
  // that are themes give us its theme membership.
  const papersByTheme = {};
  graph
    .filterNodes((_, attrs) => attrs.kind === 'paper')
    .forEach((paperId) => {
      const themeId = graph.filterOutNeighbors(paperId, (_, a) => a.kind === 'theme')[0];
      if (!themeId) return;
      (papersByTheme[themeId] ||= []).push(paperId);
    });

  Object.entries(papersByTheme).forEach(([themeId, paperIds]) => {
    const baseAngle = themeAngle[themeId] ?? 0;
    const sector = Math.min(1.2, 0.18 + paperIds.length * 0.05);
    paperIds.forEach((paperId, j) => {
      const offset = paperIds.length > 1 ? (j / (paperIds.length - 1) - 0.5) * sector : 0;
      const angle = baseAngle + offset;
      const x = RADIUS.paper * Math.cos(angle);
      const y = RADIUS.paper * Math.sin(angle);
      graph.mergeNodeAttributes(paperId, { x, y, baseX: x, baseY: y });
    });
  });

  // Claims — placed near the paper they're evidenced by.
  // `evidenced_by` edges point claim -> paper.
  const claimsByPaper = {};
  graph
    .filterNodes((_, attrs) => attrs.kind === 'claim')
    .forEach((claimId) => {
      const paperId = graph.filterOutNeighbors(claimId, (_, a) => a.kind === 'paper')[0];
      if (!paperId) return;
      (claimsByPaper[paperId] ||= []).push(claimId);
    });

  Object.entries(claimsByPaper).forEach(([paperId, claimIds]) => {
    const px = graph.getNodeAttribute(paperId, 'baseX') ?? 0;
    const py = graph.getNodeAttribute(paperId, 'baseY') ?? 0;
    const baseAngle = Math.atan2(py, px);
    const sector = Math.min(0.6, 0.1 + claimIds.length * 0.04);
    claimIds.forEach((claimId, k) => {
      const offset = claimIds.length > 1 ? (k / (claimIds.length - 1) - 0.5) * sector : 0;
      const angle = baseAngle + offset;
      const x = RADIUS.claim * Math.cos(angle);
      const y = RADIUS.claim * Math.sin(angle);
      graph.mergeNodeAttributes(claimId, { x, y, baseX: x, baseY: y });
    });
  });
}

export { RADIUS };

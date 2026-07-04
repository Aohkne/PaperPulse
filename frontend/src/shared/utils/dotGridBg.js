// Shared paper-grain background helper. Sections that paint their own
// opaque background color (to alternate paper-bg/paper-surface tone for
// visual rhythm down a long page) paint OVER body's dot-grain texture
// (index.css) within their bounds, so they need the same radial-gradient
// dot layered back on explicitly. Originally lived only in LandingPage.jsx;
// pulled out here once content-landing pages needed the same treatment too.
export const dotGridBg = (colorVar) => ({
  backgroundColor: `var(${colorVar})`,
  backgroundImage: 'radial-gradient(var(--dot-color) 1px, transparent 1px)',
  backgroundSize: '4px 4px',
});

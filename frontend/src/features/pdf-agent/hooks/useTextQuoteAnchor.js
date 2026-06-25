/**
 * Port of `backend/module/pdf_agent/services/text_quote_selector.py::refind_anchor()`.
 * Re-finds an annotation's anchor (exact/prefix/suffix) in the current editor buffer —
 * disambiguates repeated `exact` text via prefix/suffix, returns null (not found, i.e.
 * the user edited that exact spot) rather than guessing.
 */
export function refindAnchor(currentText, anchor) {
  const exact = anchor?.exact ?? '';
  if (!exact) return null;

  const candidates = [];
  let from = 0;
  while (true) {
    const idx = currentText.indexOf(exact, from);
    if (idx === -1) break;
    candidates.push(idx);
    from = idx + 1;
  }
  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0];

  const prefix = anchor.prefix ?? '';
  const suffix = anchor.suffix ?? '';
  for (const pos of candidates) {
    const prefixOk = prefix ? currentText.slice(Math.max(0, pos - prefix.length), pos).endsWith(prefix.slice(-32)) : true;
    const end = pos + exact.length;
    const suffixOk = suffix ? currentText.slice(end, end + suffix.length).startsWith(suffix.slice(0, 32)) : true;
    if (prefixOk && suffixOk) return pos;
  }
  return null;
}

/**
 * Re-anchor every (pending) annotation against `text`, returning only the ones that
 * still match, each augmented with `{ start, end }` character offsets. Debounce the
 * caller's invocation (~300ms) since this re-scans the whole buffer per call.
 */
export function reanchorAnnotations(text, annotations) {
  const result = [];
  for (const a of annotations) {
    if (a.status !== 'pending') continue;
    const start = refindAnchor(text, a.anchor);
    if (start === null) continue;
    result.push({ ...a, start, end: start + a.anchor.exact.length });
  }
  return result;
}

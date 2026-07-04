import { useMemo } from 'react';
import { MathJax } from 'better-react-mathjax';

// ── Block-level LaTeX parsing (best-effort — not a full TeX engine) ─────────

function parseLatexBlocks(raw) {
  const docMatch = raw.match(/\\begin\{document\}([\s\S]*?)\\end\{document\}/);
  const body = docMatch ? docMatch[1] : raw;

  const blocks = [];
  const listStack = [];
  const enumCounters = [];
  let inVerbatim = false;
  let inDisplayMath = false;
  let mathBuf = [];

  for (const rawLine of body.split('\n')) {
    const line = rawLine.trim();

    if (inDisplayMath) {
      if (line === '\\]' || line === '\\end{equation}' || line === '\\end{equation*}') {
        blocks.push({ type: 'displaymath', text: mathBuf.join('\n') });
        mathBuf = [];
        inDisplayMath = false;
      } else {
        mathBuf.push(rawLine);
      }
      continue;
    }

    if (inVerbatim) {
      if (line === '\\end{verbatim}') inVerbatim = false;
      else blocks.push({ type: 'verbatim', text: rawLine });
      continue;
    }

    if (!line) { blocks.push({ type: 'blank' }); continue; }
    if (line.startsWith('%')) continue;
    if (line === '\\maketitle') continue;
    if (/^\\(title|author|date)\{/.test(line)) continue;
    if (/^\\(documentclass|usepackage)\b/.test(line) || line === '\\begin{document}' || line === '\\end{document}') continue;
    if (/^\\begin\{thebibliography\}/.test(line)) { blocks.push({ type: 'bibsection_start' }); continue; }
    if (line === '\\end{thebibliography}') { blocks.push({ type: 'bibsection_end' }); continue; }
    const bibM = line.match(/^\\bibitem\{([^}]*)\}/);
    if (bibM) { blocks.push({ type: 'bibitem', key: bibM[1] }); continue; }
    if (line === '\\begin{verbatim}') { inVerbatim = true; continue; }
    if (line === '\\[' || line === '\\begin{equation}' || line === '\\begin{equation*}') {
      inDisplayMath = true;
      continue;
    }

    let m = line.match(/^\\section\*?\{(.*)\}\s*$/);
    if (m) { blocks.push({ type: 'h1', text: m[1] }); continue; }
    m = line.match(/^\\subsection\*?\{(.*)\}\s*$/);
    if (m) { blocks.push({ type: 'h2', text: m[1] }); continue; }
    m = line.match(/^\\subsubsection\*?\{(.*)\}\s*$/);
    if (m) { blocks.push({ type: 'h3', text: m[1] }); continue; }

    // Markdown fallback (legacy content saved before the LaTeX migration)
    m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) {
      const type = m[1].length === 1 ? 'h1' : m[1].length === 2 ? 'h2' : 'h3';
      blocks.push({ type, text: m[2] });
      continue;
    }
    m = line.match(/^>\s?(.*)$/);
    if (m) { blocks.push({ type: 'mdquote', text: m[1] }); continue; }

    if (line === '\\begin{itemize}') { listStack.push('itemize'); continue; }
    if (line === '\\begin{enumerate}') { listStack.push('enumerate'); enumCounters.push(0); continue; }
    if (line === '\\end{itemize}') { if (listStack[listStack.length - 1] === 'itemize') listStack.pop(); continue; }
    if (line === '\\end{enumerate}') {
      if (listStack[listStack.length - 1] === 'enumerate') { listStack.pop(); enumCounters.pop(); }
      continue;
    }
    if (line === '\\begin{quote}') { blocks.push({ type: 'quote_start' }); continue; }
    if (line === '\\end{quote}') { blocks.push({ type: 'quote_end' }); continue; }

    m = line.match(/^\\item\s*(.*)$/);
    if (m) {
      const text = m[1];
      if (listStack[listStack.length - 1] === 'enumerate') {
        enumCounters[enumCounters.length - 1] += 1;
        blocks.push({ type: 'item_num', num: enumCounters[enumCounters.length - 1], text });
      } else {
        blocks.push({ type: 'item', text });
      }
      continue;
    }

    if (/^[-=]{3,}$/.test(line) || line === '\\hrulefill') { blocks.push({ type: 'hr' }); continue; }

    // Markdown list fallback
    m = line.match(/^[-*+]\s+(.*)$/);
    if (m) { blocks.push({ type: 'item', text: m[1] }); continue; }
    m = line.match(/^(\d+)\.\s+(.*)$/);
    if (m) { blocks.push({ type: 'item_num', num: Number(m[1]), text: m[2] }); continue; }

    blocks.push({ type: 'para', text: line });
  }

  return blocks;
}

// ── Inline LaTeX → React rendering ───────────────────────────────────────────

// Each alternative is a normal regex literal (easy to eyeball-verify) — combined
// via `.source` so there's no string-escaping translation layer to get wrong.
const INLINE_RE = new RegExp(
  [
    /\\url\{(?<urlOnly>[^{}]*)\}/,
    /\\href\{(?<hrefUrl>[^{}]*)\}\{(?<hrefText>[^{}]*)\}/,
    /\\cite[tp]?\{(?<cite>[^{}]*)\}/,
    /\(Source:\s*(?<sourceCite>[^)]+)\)/,
    /\\textbf\{(?<bf>[^{}]*)\}/,
    /\\textit\{(?<it>[^{}]*)\}/,
    /\\emph\{(?<emph>[^{}]*)\}/,
    /\$(?<math1>[^$]+)\$/,
    /\\\((?<math2>[\s\S]+?)\\\)/,
    /\\\\/,
    /\\textbackslash\{\}/,
    /\\textasciitilde\{\}/,
    /\\textasciicircum\{\}/,
    /\\%/, /\\&/, /\\\$/, /\\#/, /\\_/, /\\\{/, /\\\}/,
    // Markdown fallback (legacy content saved before the LaTeX migration)
    /\*\*(?<mdbf>[^*]+)\*\*/,
    /\*(?<mdit>[^*]+)\*/,
    /__(?<mdbf2>[^_]+)__/,
    /`(?<mdcode>[^`]+)`/,
    /\[(?<mdlinktext>[^\]]+)\]\((?<mdlinkurl>[^)]+)\)/,
  ].map((r) => r.source).join('|'),
  'g',
);

const LITERAL_MAP = {
  '\\%': '%', '\\&': '&', '\\$': '$', '\\#': '#', '\\_': '_', '\\{': '{', '\\}': '}',
  '\\textbackslash{}': '\\', '\\textasciitilde{}': '~', '\\textasciicircum{}': '^',
};

const citationStyle = {
  fontSize: '11px', background: 'var(--color-paper-surface)', color: 'var(--color-paper-mid)',
  padding: '1px 5px', borderRadius: '3px', fontFamily: 'monospace',
};

const citationLinkStyle = {
  ...citationStyle,
  color: 'var(--color-brand-600)',
  textDecoration: 'none',
  cursor: 'pointer',
};

const linkStyle = { color: 'var(--color-brand-600)', textDecoration: 'underline', textUnderlineOffset: '2px' };

// Maps \bibitem{key} → its position + full reference text, so inline \cite{key}
// markers can link straight to the matching entry (and show its title on
// hover) instead of being a dead, untraceable "(key)" span — this is what lets
// a user actually tell which paper a citation refers to without scrolling.
function extractBibliography(blocks) {
  const indexByKey = new Map();
  const textByKey = new Map();
  let n = 0;
  for (let i = 0; i < blocks.length; i++) {
    if (blocks[i].type !== 'bibitem') continue;
    const key = blocks[i].key;
    n += 1;
    indexByKey.set(key, n);
    let j = i + 1;
    const textParts = [];
    while (j < blocks.length && blocks[j].type === 'para') { textParts.push(blocks[j].text); j++; }
    textByKey.set(key, textParts.join(' ').trim());
  }
  return { indexByKey, textByKey };
}

function jumpToCitation(citeKey) {
  document.getElementById(`cite-${citeKey}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Renders a \cite{key1,key2,...} group as one clickable badge per key, linking
// to its \bibitem entry below (with the reference text as a hover tooltip) —
// falls back to a plain, unclickable badge if the key isn't in the bibliography
// (e.g. content saved before export finished, or a key that was never resolved).
function renderCiteKeys(rawKeys, keyPrefix, bibliography) {
  const keys = rawKeys.split(',').map((k) => k.trim()).filter(Boolean);
  return keys.map((citeKey, i) => {
    const refText = bibliography?.textByKey.get(citeKey);
    const refIndex = bibliography?.indexByKey.get(citeKey);
    const nodeKey = `${keyPrefix}-${i}`;
    if (refIndex === undefined) {
      return <span key={nodeKey} style={citationStyle}>({citeKey})</span>;
    }
    return (
      <span
        key={nodeKey}
        role="link"
        tabIndex={0}
        title={refText || citeKey}
        onClick={() => jumpToCitation(citeKey)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') jumpToCitation(citeKey); }}
        style={citationLinkStyle}
      >
        [{refIndex}]
      </span>
    );
  });
}

function renderInline(text, keyPrefix, bibliography) {
  const nodes = [];
  let lastIndex = 0;
  let idx = 0;

  for (const m of text.matchAll(INLINE_RE)) {
    if (m.index > lastIndex) nodes.push(text.slice(lastIndex, m.index));
    const g = m.groups || {};
    const key = `${keyPrefix}-${idx++}`;

    if (g.urlOnly !== undefined) {
      const display = g.urlOnly.replace(/^https?:\/\/(www\.)?/, '').slice(0, 60);
      nodes.push(<a key={key} href={g.urlOnly} target="_blank" rel="noopener noreferrer" style={linkStyle}>{display}</a>);
    } else if (g.hrefText !== undefined) {
      nodes.push(<a key={key} href={g.hrefUrl} target="_blank" rel="noopener noreferrer" style={linkStyle}>{g.hrefText}</a>);
    } else if (g.cite !== undefined) {
      nodes.push(...renderCiteKeys(g.cite, key, bibliography));
    } else if (g.sourceCite !== undefined) {
      nodes.push(<span key={key} style={citationStyle}>(Source: {g.sourceCite})</span>);
    } else if (g.bf !== undefined) {
      nodes.push(<strong key={key}>{renderInline(g.bf, key, bibliography)}</strong>);
    } else if (g.it !== undefined) {
      nodes.push(<em key={key}>{renderInline(g.it, key, bibliography)}</em>);
    } else if (g.emph !== undefined) {
      nodes.push(<em key={key}>{renderInline(g.emph, key, bibliography)}</em>);
    } else if (g.math1 !== undefined) {
      nodes.push(<MathJax key={key} inline dynamic>{`\\(${g.math1}\\)`}</MathJax>);
    } else if (g.math2 !== undefined) {
      nodes.push(<MathJax key={key} inline dynamic>{`\\(${g.math2}\\)`}</MathJax>);
    } else if (g.mdlinktext !== undefined) {
      nodes.push(<a key={key} href={g.mdlinkurl} target="_blank" rel="noopener noreferrer" style={linkStyle}>{g.mdlinktext}</a>);
    } else if (g.mdbf !== undefined) {
      nodes.push(<strong key={key}>{renderInline(g.mdbf, key, bibliography)}</strong>);
    } else if (g.mdbf2 !== undefined) {
      nodes.push(<strong key={key}>{renderInline(g.mdbf2, key, bibliography)}</strong>);
    } else if (g.mdit !== undefined) {
      nodes.push(<em key={key}>{renderInline(g.mdit, key, bibliography)}</em>);
    } else if (g.mdcode !== undefined) {
      nodes.push(<code key={key} style={citationStyle}>{g.mdcode}</code>);
    } else if (m[0] === '\\\\') {
      nodes.push(<br key={key} />);
    } else {
      nodes.push(LITERAL_MAP[m[0]] ?? m[0]);
    }
    lastIndex = m.index + m[0].length;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

// ── Typography ────────────────────────────────────────────────────────────

const styles = {
  h1: { fontFamily: "'Newsreader', serif", fontSize: '22px', fontWeight: 700, color: 'var(--color-paper-dark)', margin: '20px 0 10px' },
  h2: { fontFamily: "'Newsreader', serif", fontSize: '18px', fontWeight: 700, color: 'var(--color-paper-dark)', margin: '16px 0 8px' },
  h3: { fontFamily: "'Newsreader', serif", fontSize: '17px', fontWeight: 600, color: 'var(--color-paper-dark)', margin: '12px 0 6px' },
  p: { fontFamily: "'Newsreader', serif", fontSize: '16px', lineHeight: '1.75', color: 'var(--color-paper-dark)', margin: '0 0 12px' },
  li: { fontFamily: "'Newsreader', serif", fontSize: '16px', lineHeight: '1.7', color: 'var(--color-paper-dark)', marginBottom: '4px' },
  list: { margin: '6px 0 12px', paddingLeft: '22px' },
  hr: { border: 'none', borderTop: '1px solid var(--color-paper-light)', margin: '18px 0' },
  blockquote: { borderLeft: '3px solid var(--color-paper-light)', paddingLeft: '14px', margin: '10px 0', color: 'var(--color-paper-mid)', fontStyle: 'italic', fontFamily: "'Newsreader', serif", fontSize: '16px' },
  pre: { background: 'var(--color-paper-surface)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '12px', overflowX: 'auto', margin: '10px 0' },
  code: { fontFamily: 'monospace', fontSize: '13px', lineHeight: '1.6' },
  empty: { fontFamily: "'Newsreader', serif", fontSize: '14px', color: 'var(--color-paper-mid)', fontStyle: 'italic' },
};

const LatexPreview = ({ content, emptyText = 'Nothing to preview yet.' }) => {
  const blocks = useMemo(() => parseLatexBlocks(content || ''), [content]);
  const bibliography = useMemo(() => extractBibliography(blocks), [blocks]);

  if (!content || !content.trim()) {
    return <span style={styles.empty}>{emptyText}</span>;
  }

  const elements = [];
  let key = 0;
  let i = 0;

  while (i < blocks.length) {
    const b = blocks[i];

    if (b.type === 'h1') { elements.push(<h1 key={key++} style={styles.h1}>{renderInline(b.text, `h1-${key}`, bibliography)}</h1>); i++; continue; }
    if (b.type === 'h2') { elements.push(<h2 key={key++} style={styles.h2}>{renderInline(b.text, `h2-${key}`, bibliography)}</h2>); i++; continue; }
    if (b.type === 'h3') { elements.push(<h3 key={key++} style={styles.h3}>{renderInline(b.text, `h3-${key}`, bibliography)}</h3>); i++; continue; }
    if (b.type === 'hr') { elements.push(<hr key={key++} style={styles.hr} />); i++; continue; }
    if (b.type === 'displaymath') {
      elements.push(<MathJax key={key++} dynamic>{`\\[${b.text}\\]`}</MathJax>);
      i++;
      continue;
    }

    if (b.type === 'verbatim') {
      const lines = [];
      while (i < blocks.length && blocks[i].type === 'verbatim') { lines.push(blocks[i].text); i++; }
      elements.push(<pre key={key++} style={styles.pre}><code style={styles.code}>{lines.join('\n')}</code></pre>);
      continue;
    }

    if (b.type === 'item' || b.type === 'item_num') {
      const groupType = b.type;
      const items = [];
      while (i < blocks.length && blocks[i].type === groupType) { items.push(blocks[i]); i++; }
      const ListTag = groupType === 'item_num' ? 'ol' : 'ul';
      elements.push(
        <ListTag key={key++} style={styles.list}>
          {items.map((it, idx) => <li key={idx} style={styles.li}>{renderInline(it.text, `li-${key}-${idx}`, bibliography)}</li>)}
        </ListTag>,
      );
      continue;
    }

    if (b.type === 'mdquote') {
      const lines = [];
      while (i < blocks.length && blocks[i].type === 'mdquote') { lines.push(blocks[i].text); i++; }
      elements.push(<blockquote key={key++} style={styles.blockquote}>{renderInline(lines.join(' '), `mdq-${key}`, bibliography)}</blockquote>);
      continue;
    }

    if (b.type === 'quote_start') {
      i++;
      const innerText = [];
      while (i < blocks.length && blocks[i].type !== 'quote_end') {
        if (blocks[i].type === 'para') innerText.push(blocks[i].text);
        i++;
      }
      i++; // skip quote_end
      elements.push(<blockquote key={key++} style={styles.blockquote}>{renderInline(innerText.join(' '), `bq-${key}`, bibliography)}</blockquote>);
      continue;
    }

    if (b.type === 'bibsection_start') {
      i++;
      const entries = [];
      while (i < blocks.length && blocks[i].type !== 'bibsection_end') {
        if (blocks[i].type === 'bibitem') {
          const entryKey = blocks[i].key;
          i++;
          const textParts = [];
          while (i < blocks.length && blocks[i].type === 'para') { textParts.push(blocks[i].text); i++; }
          while (i < blocks.length && blocks[i].type === 'blank') i++;
          entries.push({ key: entryKey, text: textParts.join(' ').trim() });
        } else {
          i++;
        }
      }
      i++; // skip bibsection_end
      if (entries.length > 0) {
        elements.push(
          <div key={key++}>
            <h2 style={styles.h1}>References</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '8px' }}>
              {entries.map((entry, idx) => (
                <div key={idx} id={`cite-${entry.key}`} style={{ display: 'flex', gap: '8px', fontSize: '13px', lineHeight: '1.6', fontFamily: "'Newsreader', serif", color: 'var(--color-paper-dark)' }}>
                  <span style={{ minWidth: '24px', color: 'var(--color-paper-mid)', flexShrink: 0, paddingTop: '1px' }}>[{idx + 1}]</span>
                  <span>{renderInline(entry.text, `bib-${key}-${idx}`, bibliography)}</span>
                </div>
              ))}
            </div>
          </div>
        );
      }
      continue;
    }

    if (b.type === 'bibsection_end' || b.type === 'bibitem') { i++; continue; }

    if (b.type === 'blank') { i++; continue; }

    if (b.type === 'para') {
      const lines = [];
      while (i < blocks.length && blocks[i].type === 'para') { lines.push(blocks[i].text); i++; }
      elements.push(<p key={key++} style={styles.p}>{renderInline(lines.join(' '), `p-${key}`, bibliography)}</p>);
      continue;
    }

    i++; // unknown block — skip
  }

  return <div>{elements}</div>;
};

export default LatexPreview;

import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import Editor from '@monaco-editor/react';
import { registerLatexLanguage } from '@/shared/utils/monacoLatex';
import { reanchorAnnotations } from '@/features/pdf-agent/hooks/useTextQuoteAnchor';

const DECORATION_STYLE_ID = 'pdfagent-decoration-styles';

function ensureDecorationStyles() {
  if (document.getElementById(DECORATION_STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = DECORATION_STYLE_ID;
  style.textContent = `
    .pdfagent-deco-suggest { text-decoration: underline wavy #b8860b; background: rgba(184,134,11,0.10); cursor: pointer; }
    .pdfagent-deco-warning { text-decoration: underline wavy #c0392b; background: rgba(192,57,43,0.10); cursor: pointer; }
  `;
  document.head.appendChild(style);
}

/**
 * Monaco editor + inline decorations for pending suggest/warning annotations.
 * Re-anchors against the *current* buffer on every change (debounced ~300ms per
 * PLAN §7 Phase 6) — an annotation whose exact text no longer matches simply stops
 * being decorated (it "disappears" without an error, per the PLAN's anchor contract).
 */
const TexEditor = forwardRef(function TexEditor(
  { value, onChange, annotations, onAnnotationClick, onSelectionChange },
  ref
) {
  const editorRef = useRef(null);
  const monacoRef = useRef(null);
  const decorationIdsRef = useRef([]);
  const decoratedRangesRef = useRef([]); // [{id, startOffset, endOffset}]
  const debounceRef = useRef(null);
  const selectionDebounceRef = useRef(null);

  useImperativeHandle(ref, () => ({
    revealAnnotation(annotationId) {
      const editor = editorRef.current;
      const match = decoratedRangesRef.current.find((d) => d.id === annotationId);
      if (!editor || !match) return;
      const model = editor.getModel();
      const start = model.getPositionAt(match.startOffset);
      const end = model.getPositionAt(match.endOffset);
      const monaco = monacoRef.current;
      const range = new monaco.Range(start.lineNumber, start.column, end.lineNumber, end.column);
      editor.revealRangeInCenter(range);
      editor.setSelection(range);
    },
  }));

  const recomputeDecorations = () => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) return;
    const model = editor.getModel();
    const matched = reanchorAnnotations(value, annotations);
    decoratedRangesRef.current = matched.map((m) => ({
      id: m.id,
      startOffset: m.start,
      endOffset: m.end,
    }));

    const newDecorations = matched.map((m) => {
      const start = model.getPositionAt(m.start);
      const end = model.getPositionAt(m.end);
      return {
        range: new monaco.Range(start.lineNumber, start.column, end.lineNumber, end.column),
        options: {
          inlineClassName: m.type === 'warning' ? 'pdfagent-deco-warning' : 'pdfagent-deco-suggest',
          hoverMessage: { value: m.comment },
        },
      };
    });
    decorationIdsRef.current = editor.deltaDecorations(decorationIdsRef.current, newDecorations);
  };

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(recomputeDecorations, 300);
    return () => clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, annotations]);

  const handleMount = (editor, monaco) => {
    ensureDecorationStyles();
    registerLatexLanguage(monaco);
    editorRef.current = editor;
    monacoRef.current = monaco;
    recomputeDecorations();

    editor.onMouseDown((e) => {
      if (!e.target.position) return;
      const offset = editor.getModel().getOffsetAt(e.target.position);
      const hit = decoratedRangesRef.current.find(
        (d) => offset >= d.startOffset && offset < d.endOffset
      );
      if (hit) onAnnotationClick?.(hit.id);
    });

    editor.onDidChangeCursorSelection((e) => {
      // Fires on every pointer-move tick while dragging a selection — debounce
      // so the toolbar/parent state doesn't re-render on each tick (was causing
      // visible jank while click-dragging across text).
      const sel = e.selection;
      clearTimeout(selectionDebounceRef.current);
      selectionDebounceRef.current = setTimeout(() => {
        if (sel.isEmpty()) {
          onSelectionChange?.(null);
          return;
        }
        const model = editor.getModel();
        const selectedText = model.getValueInRange(sel);
        if (!selectedText.trim()) {
          onSelectionChange?.(null);
          return;
        }
        const startOffset = model.getOffsetAt(sel.getStartPosition());
        const endOffset = model.getOffsetAt(sel.getEndPosition());
        const fullText = model.getValue();
        const prefix = fullText.slice(Math.max(0, startOffset - 32), startOffset);
        const suffix = fullText.slice(endOffset, endOffset + 32);
        onSelectionChange?.({ selectedText, prefix, suffix });
      }, 90);
    });
  };

  return (
    <Editor
      language="latex"
      theme="vs"
      value={value}
      onChange={(v) => onChange(v ?? '')}
      onMount={handleMount}
      options={{
        fontSize: 13,
        fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
        wordWrap: 'on',
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
      }}
    />
  );
});

export default TexEditor;

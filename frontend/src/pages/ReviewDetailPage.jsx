import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import Editor from '@monaco-editor/react';
import LatexPreview from '@/shared/components/LatexPreview';
import { registerLatexLanguage } from '@/shared/utils/monacoLatex';
import { useReviewsStore } from '@/shared/store/useReviewsStore';
import { reviewsApi } from '@/features/reviews/reviewsApi';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { ROUTES } from '@/shared/constant/routes';
import { showSuccess, showError } from '@/shared/utils/toast';
import { friendlyError } from '@/shared/utils/errorMessage';

const getToken = () => useAuthStore.getState().token;

const ReviewDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { current, detailLoading, detailError, fetchDetail, updateCurrent, deleteReview } = useReviewsStore();
  const [editMode, setEditMode] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportMenuRef = useRef(null);
  const editorRef = useRef(null);
  const previewRef = useRef(null);
  const syncingRef = useRef(false);

  useEffect(() => { fetchDetail(id); }, [id, fetchDetail]);

  // Sync local edit fields when a new review loads — adjusted during render
  // instead of in an effect (React docs: "You Might Not Need an Effect").
  const [prevCurrent, setPrevCurrent] = useState(current);
  if (current !== prevCurrent) {
    setPrevCurrent(current);
    if (current) {
      setEditTitle(current.title);
      setEditContent(current.markdown_content);
    }
  }

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateCurrent(id, { title: editTitle.trim(), markdown_content: editContent });
      setEditMode(false);
      showSuccess('Changes saved.');
    } catch (e) {
      showError(e, "Couldn't save your changes — please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Delete this review?')) return;
    try {
      await deleteReview(id);
      navigate(ROUTES.MY_REVIEWS);
    } catch (e) {
      showError(e, "Couldn't delete this review — please try again.");
    }
  };

  useEffect(() => {
    if (!exportMenuOpen) return;
    const handler = (e) => { if (!exportMenuRef.current?.contains(e.target)) setExportMenuOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportMenuOpen]);

  const handleExport = async (format) => {
    setExportMenuOpen(false);
    setExportLoading(true);
    try {
      await reviewsApi.download(getToken(), id, format);
    } catch (e) {
      showError(e, "Couldn't export this review — please try again.");
    } finally {
      setExportLoading(false);
    }
  };

  const handleEditorMount = (editor, monaco) => {
    registerLatexLanguage(monaco);
    editorRef.current = editor;
    editor.onDidScrollChange(() => {
      if (syncingRef.current) return;
      const pr = previewRef.current;
      if (!pr) return;
      syncingRef.current = true;
      const scrollTop = editor.getScrollTop();
      const scrollHeight = editor.getScrollHeight();
      const layoutHeight = editor.getLayoutInfo().height;
      const pct = scrollTop / (scrollHeight - layoutHeight || 1);
      pr.scrollTop = pct * (pr.scrollHeight - pr.clientHeight);
      requestAnimationFrame(() => { syncingRef.current = false; });
    });
  };

  const handlePreviewScroll = () => {
    if (syncingRef.current) return;
    const ed = editorRef.current;
    const pr = previewRef.current;
    if (!ed || !pr) return;
    syncingRef.current = true;
    const pct = pr.scrollTop / (pr.scrollHeight - pr.clientHeight || 1);
    const scrollHeight = ed.getScrollHeight();
    const layoutHeight = ed.getLayoutInfo().height;
    ed.setScrollTop(pct * (scrollHeight - layoutHeight));
    requestAnimationFrame(() => { syncingRef.current = false; });
  };

  const handleCancel = () => {
    setEditMode(false);
    setEditTitle(current.title);
    setEditContent(current.markdown_content);
  };

  if (detailLoading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon icon="mdi:loading" style={{ width: 28, height: 28, color: 'var(--color-paper-light)', animation: 'spin 1s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (detailError) {
    return (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
        <span style={{ fontFamily: "'Noto Serif', serif", color: '#c0392b' }}>{friendlyError(detailError, "Couldn't load this review.")}</span>
        <button onClick={() => navigate(-1)} style={{ fontFamily: "'Noto Serif', serif", fontSize: '14px', cursor: 'pointer', color: 'var(--color-paper-mid)', background: 'none', border: 'none' }}>
          ← Back
        </button>
      </div>
    );
  }

  if (!current) return null;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div style={{
        flexShrink: 0,
        borderBottom: '1px solid var(--color-paper-light)',
        padding: '10px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        background: 'var(--color-paper-bg)',
      }}>
        <button
          onClick={() => navigate(ROUTES.MY_REVIEWS)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-mid)', padding: 0, display: 'flex', alignItems: 'center', gap: '4px', fontFamily: "'Noto Serif', serif", fontSize: '13px', flexShrink: 0 }}
        >
          <Icon icon="mdi:arrow-left" style={{ width: 15, height: 15 }} />
          My Reviews
        </button>

        <div style={{ width: '1px', height: '16px', background: 'var(--color-paper-light)', flexShrink: 0 }} />

        {/* Title — editable inline when in edit mode */}
        {editMode ? (
          <input
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            style={{
              flex: 1, minWidth: 0,
              fontFamily: "'Noto Serif', serif", fontSize: '14px', fontWeight: 600,
              color: 'var(--color-paper-dark)',
              border: '1px solid var(--color-paper-light)',
              borderRadius: '4px', padding: '4px 8px',
              background: 'var(--color-paper-surface)', outline: 'none',
            }}
          />
        ) : (
          <span style={{ flex: 1, minWidth: 0, fontFamily: "'Noto Serif', serif", fontSize: '14px', fontWeight: 600, color: 'var(--color-paper-dark)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {current.title}
          </span>
        )}

        <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
          {/* Export dropdown */}
          <div style={{ position: 'relative' }} ref={exportMenuRef}>
            <button
              onClick={() => setExportMenuOpen((v) => !v)}
              disabled={exportLoading}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '4px 9px', background: 'none', cursor: exportLoading ? 'wait' : 'pointer' }}
            >
              {exportLoading
                ? <Icon icon="mdi:loading" style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} />
                : <Icon icon="mdi:download-outline" style={{ width: 13, height: 13 }} />}
              Export
              <Icon icon="mdi:chevron-down" style={{ width: 12, height: 12 }} />
            </button>
            <AnimatePresence>
              {exportMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.12 }}
                  style={{ position: 'absolute', right: 0, top: '32px', background: 'var(--color-paper-bg)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', boxShadow: '0 6px 20px rgba(0,0,0,0.1)', minWidth: '148px', zIndex: 200, overflow: 'hidden' }}
                >
                  {[
                    { icon: 'mdi:file-code-outline', label: 'LaTeX (.tex)', format: 'tex' },
                    { icon: 'mdi:language-markdown-outline', label: 'Markdown (.md)', format: 'markdown' },
                    { icon: 'mdi:file-pdf-box', label: 'PDF (.pdf)', format: 'pdf' },
                    { icon: 'mdi:folder-zip-outline', label: 'ZIP (.zip)', format: 'zip' },
                  ].map(({ icon, label, format }) => (
                    <button
                      key={format}
                      onClick={() => handleExport(format)}
                      style={{ width: '100%', textAlign: 'left', padding: '8px 12px', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontFamily: "'Noto Serif', serif", fontSize: '13px', color: 'var(--color-paper-dark)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-paper-surface)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                    >
                      <Icon icon={icon} style={{ width: 14, height: 14, color: 'var(--color-paper-mid)' }} />
                      {label}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {current.source_type === 'uploaded' && current.content_format === 'tex' && !editMode && (
            <button
              onClick={() => navigate(`${ROUTES.PDF_AGENT}?resume=${id}`)}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '4px 9px', background: 'none', cursor: 'pointer' }}
            >
              <Icon icon="mdi:file-search-outline" style={{ width: 13, height: 13 }} />
              Continue with PDF Agent
            </button>
          )}

          {editMode ? (
            <>
              <button
                onClick={handleCancel}
                style={{ fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '4px 9px', background: 'none', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{ fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-bg)', background: 'var(--color-paper-dark)', border: 'none', borderRadius: '4px', padding: '4px 11px', cursor: saving ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                {saving && <Icon icon="mdi:loading" style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} />}
                Save
              </button>
            </>
          ) : (
            <button
              onClick={() => setEditMode(true)}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '4px 9px', background: 'none', cursor: 'pointer' }}
            >
              <Icon icon="mdi:pencil-outline" style={{ width: 13, height: 13 }} />
              Edit
            </button>
          )}

          <button
            onClick={handleDelete}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: "'Noto Serif', serif", fontSize: '12px', color: '#c0392b', border: '1px solid #e0b0b0', borderRadius: '4px', padding: '4px 9px', background: 'none', cursor: 'pointer' }}
          >
            <Icon icon="mdi:delete-outline" style={{ width: 13, height: 13 }} />
            Delete
          </button>
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {editMode ? (
          /* Split-panel edit mode */
          <motion.div
            key="split"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            style={{ flex: 1, display: 'flex', overflow: 'hidden' }}
          >
            {/* Left: editor */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRight: '1px solid var(--color-paper-light)' }}>
              <div style={{ flexShrink: 0, padding: '8px 14px', borderBottom: '1px solid var(--color-paper-light)', display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--color-paper-surface)' }}>
                <Icon icon="mdi:code-tags" style={{ width: 13, height: 13, color: 'var(--color-paper-mid)' }} />
                <span style={{ fontFamily: "'Noto Serif', serif", fontSize: '11px', fontWeight: 600, color: 'var(--color-paper-mid)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>LaTeX</span>
              </div>
              <div style={{ flex: 1, minHeight: 0 }}>
                <Editor
                  language="latex"
                  theme="vs"
                  value={editContent}
                  onChange={(value) => setEditContent(value ?? '')}
                  onMount={handleEditorMount}
                  options={{
                    fontSize: 13,
                    fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace',
                    wordWrap: 'on',
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                  }}
                />
              </div>
            </div>

            {/* Right: preview */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ flexShrink: 0, padding: '8px 14px', borderBottom: '1px solid var(--color-paper-light)', display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--color-paper-bg)' }}>
                <Icon icon="mdi:eye-outline" style={{ width: 13, height: 13, color: 'var(--color-paper-mid)' }} />
                <span style={{ fontFamily: "'Noto Serif', serif", fontSize: '11px', fontWeight: 600, color: 'var(--color-paper-mid)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Preview</span>
              </div>
              <div ref={previewRef} onScroll={handlePreviewScroll} style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
                <LatexPreview content={editContent} emptyText="Start typing to see the preview..." />
              </div>
            </div>
          </motion.div>
        ) : (
          /* View mode: centered single column */
          <motion.div
            key="view"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            style={{ flex: 1, overflowY: 'auto', padding: '32px 24px' }}
          >
            <div style={{ maxWidth: '720px', margin: '0 auto' }}>
              <h1 style={{ fontFamily: "'Noto Serif', serif", fontSize: '22px', fontWeight: 700, color: 'var(--color-paper-dark)', margin: '0 0 4px' }}>
                {current.title}
              </h1>
              <div style={{ fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-light)', marginBottom: '24px' }}>
                {new Date(current.updated_at).toLocaleString()} · {current.query}
              </div>
              <hr style={{ border: 'none', borderTop: '1px solid var(--color-paper-light)', marginBottom: '24px' }} />
              <LatexPreview content={current.markdown_content} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default ReviewDetailPage;

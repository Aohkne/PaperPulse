import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { usePdfAgentStore } from '@/features/pdf-agent/store/usePdfAgentStore';
import { pdfAgentApi } from '@/features/pdf-agent/pdfAgentApi';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import PDFUploadZone from '@/features/pdf-agent/components/PDFUploadZone';
import TexEditor from '@/features/pdf-agent/components/TexEditor';
import AnnotationCard from '@/features/pdf-agent/components/AnnotationCard';
import SelectionToolbar from '@/features/pdf-agent/components/SelectionToolbar';
import RewritePreview from '@/features/pdf-agent/components/RewritePreview';
import { ROUTES } from '@/shared/constant/routes';

const getToken = () => useAuthStore.getState().token;

const Toast = ({ message, success }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0 }}
    style={{
      position: 'fixed', bottom: '24px', left: '50%', transform: 'translateX(-50%)',
      background: success ? 'var(--color-paper-dark)' : '#c0392b',
      color: 'var(--color-paper-bg)',
      fontFamily: 'Georgia, serif', fontSize: '14px',
      padding: '10px 20px', borderRadius: '4px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
      zIndex: 9999, whiteSpace: 'nowrap',
    }}
  >
    {message}
  </motion.div>
);

const STEP_ICONS = { running: 'mdi:loading', done: 'mdi:check-circle' };

const PDFAgentPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const resumeReviewId = searchParams.get('resume');

  const {
    docId, title, status, steps, texContent, annotations, error, reviewId, selectionResult,
    upload, setTexContent, setTitle, updateAnnotation, explainSelection, rewriteSelection,
    applyRewrite, clearSelectionResult, saveToReview, loadFromResume, reset,
  } = usePdfAgentStore();

  const [selection, setSelection] = useState(null);
  const [activeAnnotationId, setActiveAnnotationId] = useState(null);
  const [toast, setToast] = useState(null);
  const [saving, setSaving] = useState(false);
  const editorRef = useRef(null);
  const resumeAttempted = useRef(false);

  useEffect(() => {
    reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const showToast = (message, success = true) => {
    setToast({ message, success });
    setTimeout(() => setToast(null), 2500);
  };

  useEffect(() => {
    if (!resumeReviewId || resumeAttempted.current) return;
    resumeAttempted.current = true;
    (async () => {
      try {
        const res = await pdfAgentApi.resume(getToken(), resumeReviewId);
        loadFromResume({ docId: res.doc_id, title: res.title, annotations: res.annotations, texContent: '' });
        const content = await pdfAgentApi.getContent(getToken(), res.doc_id);
        setTexContent(content.tex_content);
      } catch (e) {
        showToast(e.message || 'Could not reopen this document', false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeReviewId]);

  const handleAnnotationAction = async (annotation, action) => {
    try {
      await updateAnnotation(annotation.id, action);
      showToast(action === 'accept' ? 'Accepted ✓' : action === 'reject' ? 'Rejected' : 'Dismissed');
    } catch (e) {
      showToast(e.message || 'Action failed', false);
    }
  };

  const handleExplain = () => {
    if (!selection) return;
    explainSelection(selection);
  };

  const handleRewrite = (instruction) => {
    if (!selection) return;
    rewriteSelection(selection, instruction);
  };

  const handleApply = async () => {
    try {
      await applyRewrite();
      showToast('Applied ✓');
    } catch (e) {
      showToast(e.message || 'Apply failed (has the passage changed?)', false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveToReview();
      showToast('Saved to My Reviews ✓');
    } catch (e) {
      showToast(e.message || 'Save failed', false);
    } finally {
      setSaving(false);
    }
  };

  const pendingAnnotations = annotations.filter((a) => a.status === 'pending');
  const suggestCount = pendingAnnotations.filter((a) => a.type === 'suggest').length;
  const warningCount = pendingAnnotations.filter((a) => a.type === 'warning').length;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ── Toolbar ───────────────────────────────────────────────────── */}
      <div style={{
        flexShrink: 0, borderBottom: '1px solid var(--color-paper-light)',
        padding: '10px 20px', display: 'flex', alignItems: 'center', gap: '8px',
        background: 'var(--color-paper-bg)',
      }}>
        <Icon icon="mdi:file-document-edit-outline" style={{ width: 18, height: 18, color: 'var(--color-paper-mid)', flexShrink: 0 }} />

        {status === 'ready' || status === 'saving' ? (
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{
              flex: 1, minWidth: 0, fontFamily: 'var(--font-inknut)', fontSize: '20px', fontWeight: 700,
              color: 'var(--color-paper-dark)', border: '1px solid transparent', borderRadius: '4px',
              padding: '4px 8px', background: 'none', outline: 'none',
            }}
            onFocus={(e) => (e.currentTarget.style.border = '1px solid var(--color-paper-light)')}
            onBlur={(e) => (e.currentTarget.style.border = '1px solid transparent')}
          />
        ) : (
          <span style={{ flex: 1, fontFamily: 'var(--font-inknut)', fontSize: '20px', fontWeight: 700, color: 'var(--color-paper-dark)' }}>
            PDF Agent — Style &amp; Citation Checker
          </span>
        )}

        {(status === 'ready' || status === 'saving') && (
          <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontFamily: 'Georgia, serif', fontSize: '12px', color: 'var(--color-paper-light)' }}>
              {suggestCount} suggest · {warningCount} warning
            </span>
            <button
              onClick={() => pdfAgentApi.downloadBundle(getToken(), docId)}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: 'Georgia, serif', fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '4px 9px', background: 'none', cursor: 'pointer' }}
            >
              <Icon icon="mdi:download-outline" style={{ width: 13, height: 13 }} />
              .zip
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: 'Georgia, serif', fontSize: '12px', color: 'var(--color-paper-bg)', background: 'var(--color-paper-dark)', border: 'none', borderRadius: '4px', padding: '4px 11px', cursor: saving ? 'wait' : 'pointer' }}
            >
              {saving && <Icon icon="mdi:loading" style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} />}
              Save to My Reviews
            </button>
            {reviewId && (
              <button
                onClick={() => navigate(ROUTES.REVIEW_DETAIL(reviewId))}
                style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: 'Georgia, serif', fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '4px 9px', background: 'none', cursor: 'pointer' }}
              >
                <Icon icon="mdi:open-in-new" style={{ width: 13, height: 13 }} />
                View in My Reviews
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Body ──────────────────────────────────────────────────────── */}
      {status === 'idle' && <PDFUploadZone onFile={upload} />}

      {(status === 'uploading' || status === 'streaming') && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
          <div style={{
            width: '380px', border: '1px solid var(--color-paper-light)', borderRadius: '10px',
            background: 'var(--color-paper-bg)', padding: '20px 22px',
            boxShadow: '0 8px 28px rgba(0,0,0,0.06)',
          }}>
            <div style={{ fontFamily: 'var(--font-inknut)', fontSize: '14px', fontWeight: 700, color: 'var(--color-paper-dark)', marginBottom: '14px' }}>
              Processing your document
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <AnimatePresence initial={false}>
                {steps.map((s) => (
                  <motion.div
                    key={s.node}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                    style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 0' }}
                  >
                    <div style={{
                      width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      background: s.status === 'done' ? 'rgba(31,122,61,0.12)' : 'var(--color-paper-surface)',
                    }}>
                      <Icon
                        icon={STEP_ICONS[s.status]}
                        style={{ width: 14, height: 14, color: s.status === 'done' ? '#1f7a3d' : 'var(--color-paper-mid)', animation: s.status === 'running' ? 'spin 1s linear infinite' : 'none' }}
                      />
                    </div>
                    <span style={{ fontFamily: 'Georgia, serif', fontSize: '13px', color: s.status === 'running' ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)', fontWeight: s.status === 'running' ? 600 : 400 }}>
                      {s.label}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
              {steps.length === 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 0' }}>
                  <div style={{ width: 26, height: 26, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--color-paper-surface)' }}>
                    <Icon icon="mdi:loading" style={{ width: 14, height: 14, color: 'var(--color-paper-mid)', animation: 'spin 1s linear infinite' }} />
                  </div>
                  <span style={{ fontFamily: 'Georgia, serif', fontSize: '13px', color: 'var(--color-paper-mid)' }}>Uploading...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
          <Icon icon="mdi:alert-circle-outline" style={{ width: 32, height: 32, color: '#c0392b' }} />
          <span style={{ fontFamily: 'Georgia, serif', color: '#c0392b', maxWidth: '480px', textAlign: 'center' }}>{error}</span>
          <button onClick={reset} style={{ fontFamily: 'Georgia, serif', fontSize: '14px', cursor: 'pointer', color: 'var(--color-paper-mid)', background: 'none', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '6px 14px' }}>
            Try again
          </button>
        </div>
      )}

      {(status === 'ready' || status === 'saving') && (
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {/* Left: editor */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderRight: '1px solid var(--color-paper-light)' }}>
            <SelectionToolbar selection={selection} onExplain={handleExplain} onRewrite={handleRewrite} />
            <RewritePreview result={selectionResult} onApply={handleApply} onClose={clearSelectionResult} />
            <div style={{ flex: 1, minHeight: 0 }}>
              <TexEditor
                ref={editorRef}
                value={texContent}
                onChange={setTexContent}
                annotations={annotations}
                onAnnotationClick={setActiveAnnotationId}
                onSelectionChange={setSelection}
              />
            </div>
          </div>

          {/* Right: annotations sidebar */}
          <div style={{ width: '360px', flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--color-paper-surface)' }}>
            <div style={{ flexShrink: 0, padding: '10px 14px', borderBottom: '1px solid var(--color-paper-light)' }}>
              <span style={{ fontFamily: 'Georgia, serif', fontSize: '12px', fontWeight: 600, color: 'var(--color-paper-mid)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Annotations ({pendingAnnotations.length})
              </span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
              {pendingAnnotations.length === 0 ? (
                <div style={{ fontFamily: 'Georgia, serif', fontSize: '13px', color: 'var(--color-paper-light)', textAlign: 'center', marginTop: '24px' }}>
                  No pending annotations left.
                </div>
              ) : (
                pendingAnnotations.map((a) => (
                  <AnnotationCard
                    key={a.id}
                    annotation={a}
                    active={a.id === activeAnnotationId}
                    onClick={() => {
                      setActiveAnnotationId(a.id);
                      editorRef.current?.revealAnnotation(a.id);
                    }}
                    onAction={(action) => handleAnnotationAction(a, action)}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      )}

      <AnimatePresence>{toast && <Toast key="t" message={toast.message} success={toast.success} />}</AnimatePresence>
    </div>
  );
};

export default PDFAgentPage;

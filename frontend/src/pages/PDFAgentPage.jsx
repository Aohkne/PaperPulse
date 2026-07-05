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
import { useIsMobile } from '@/shared/hooks/useIsMobile';
import { useQuotaExhausted } from '@/shared/hooks/useQuotaExhausted';
import UsageExhaustedBanner from '@/features/billing/UsageExhaustedBanner';
import { showSuccess, showError } from '@/shared/utils/toast';
import { friendlyError } from '@/shared/utils/errorMessage';

const getToken = () => useAuthStore.getState().token;

const STEP_ICONS = { running: 'mdi:loading', done: 'mdi:check-circle' };

const PDFAgentPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const resumeReviewId = searchParams.get('resume');

  const {
    docId,
    title,
    status,
    steps,
    texContent,
    annotations,
    error,
    reviewId,
    selectionResult,
    upload,
    setTexContent,
    setTitle,
    updateAnnotation,
    explainSelection,
    rewriteSelection,
    applyRewrite,
    clearSelectionResult,
    saveToReview,
    loadFromResume,
    reset,
  } = usePdfAgentStore();

  const [selection, setSelection] = useState(null);
  const [activeAnnotationId, setActiveAnnotationId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [mobileTab, setMobileTab] = useState('editor');
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const editorRef = useRef(null);
  const resumeAttempted = useRef(false);
  const exportMenuRef = useRef(null);
  const isMobile = useIsMobile(860);
  const quotaExhausted = useQuotaExhausted('pdf');

  useEffect(() => {
    if (!exportMenuOpen) return;
    const handler = (e) => {
      if (!exportMenuRef.current?.contains(e.target)) setExportMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [exportMenuOpen]);

  const handleExport = async (format) => {
    setExportMenuOpen(false);
    setExportLoading(true);
    try {
      await pdfAgentApi.download(getToken(), docId, format);
    } catch (e) {
      showError(e, 'Export failed');
    } finally {
      setExportLoading(false);
    }
  };

  useEffect(() => {
    reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!resumeReviewId || resumeAttempted.current) return;
    resumeAttempted.current = true;
    (async () => {
      try {
        const res = await pdfAgentApi.resume(getToken(), resumeReviewId);
        loadFromResume({
          docId: res.doc_id,
          title: res.title,
          annotations: res.annotations,
          texContent: '',
        });
        const content = await pdfAgentApi.getContent(getToken(), res.doc_id);
        setTexContent(content.tex_content);
      } catch (e) {
        showError(e, 'Could not reopen this document');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeReviewId]);

  const handleAnnotationAction = async (annotation, action) => {
    try {
      await updateAnnotation(annotation.id, action);
      showSuccess(
        action === 'accept' ? 'Accepted' : action === 'reject' ? 'Rejected' : 'Dismissed'
      );
    } catch (e) {
      showError(e, 'Action failed');
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
      showSuccess('Applied');
    } catch (e) {
      showError(e, 'Apply failed (has the passage changed?)');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveToReview();
      showSuccess('Saved to My Reviews');
    } catch (e) {
      showError(e, 'Save failed');
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
      <div
        style={{
          flexShrink: 0,
          boxShadow: '0 1px 3px rgba(41, 17, 0, 0.08)',
          padding: '10px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--color-paper-bg)',
          position: 'relative',
          zIndex: 1,
        }}
      >
        <Icon
          icon="mdi:file-document-edit-outline"
          style={{ width: 18, height: 18, color: 'var(--color-paper-mid)', flexShrink: 0 }}
        />

        {status === 'ready' || status === 'saving' ? (
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={{
              flex: 1,
              minWidth: 0,
              fontFamily: 'var(--font-inknut)',
              fontSize: '21px',
              fontWeight: 700,
              color: 'var(--color-paper-dark)',
              border: '1px solid transparent',
              borderRadius: '4px',
              padding: '4px 8px',
              background: 'none',
              outline: 'none',
            }}
            onFocus={(e) => (e.currentTarget.style.border = '1px solid var(--color-paper-light)')}
            onBlur={(e) => (e.currentTarget.style.border = '1px solid transparent')}
          />
        ) : (
          <span
            style={{
              flex: 1,
              fontFamily: 'var(--font-inknut)',
              fontSize: '21px',
              fontWeight: 700,
              color: 'var(--color-paper-dark)',
            }}
          >
            PDF Agent — Style &amp; Citation Checker
          </span>
        )}

        <button
          onClick={() => window.Supademo?.open('cmqyjvr8y06fjw60jr7pw2e9z')}
          title="How it works"
          style={{
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 28,
            height: 28,
            borderRadius: '50%',
            border: '1px solid var(--color-paper-light)',
            background: 'var(--color-paper-bg)',
            color: 'var(--color-paper-mid)',
            cursor: 'pointer',
          }}
        >
          {/* Plain "?" glyph (mdi:help), not mdi:help-circle-outline — that
              icon already draws its own circle, which doubled up with this
              button's own circular border into a nested ring-in-a-ring look. */}
          <Icon icon="mdi:help" style={{ width: 14, height: 14 }} />
        </button>

        {(status === 'ready' || status === 'saving') && (
          <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              style={{
                fontFamily: "'Newsreader', serif",
                fontSize: '13px',
                color: 'var(--color-paper-mid)',
              }}
            >
              {suggestCount} suggest · {warningCount} warning
            </span>
            <div style={{ position: 'relative' }} ref={exportMenuRef}>
              <button
                onClick={() => setExportMenuOpen((v) => !v)}
                disabled={exportLoading}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontFamily: "'Newsreader', serif",
                  fontSize: '13px',
                  color: 'var(--color-paper-mid)',
                  border: '1px solid var(--color-paper-light)',
                  borderRadius: '4px',
                  padding: '4px 9px',
                  background: 'none',
                  cursor: exportLoading ? 'wait' : 'pointer',
                }}
              >
                {exportLoading ? (
                  <Icon
                    icon="mdi:loading"
                    style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }}
                  />
                ) : (
                  <Icon icon="mdi:download-outline" style={{ width: 13, height: 13 }} />
                )}
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
                    style={{
                      position: 'absolute',
                      right: 0,
                      top: '32px',
                      background: 'var(--color-paper-bg)',
                      border: '1px solid var(--color-paper-light)',
                      borderRadius: '4px',
                      boxShadow: '0 6px 20px rgba(0,0,0,0.1)',
                      minWidth: '148px',
                      zIndex: 200,
                      overflow: 'hidden',
                    }}
                  >
                    {[
                      { icon: 'mdi:file-code-outline', label: 'LaTeX (.tex)', format: 'tex' },
                      { icon: 'mdi:file-pdf-box', label: 'PDF (.pdf)', format: 'pdf' },
                      { icon: 'mdi:folder-zip-outline', label: 'ZIP (.zip)', format: 'zip' },
                    ].map(({ icon, label, format }) => (
                      <button
                        key={format}
                        onClick={() => handleExport(format)}
                        style={{
                          width: '100%',
                          textAlign: 'left',
                          padding: '8px 12px',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          fontFamily: "'Newsreader', serif",
                          fontSize: '15px',
                          color: 'var(--color-paper-dark)',
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background = 'var(--color-paper-surface)')
                        }
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                      >
                        <Icon
                          icon={icon}
                          style={{ width: 14, height: 14, color: 'var(--color-paper-mid)' }}
                        />
                        {label}
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontFamily: "'Newsreader', serif",
                fontSize: '13px',
                color: 'var(--color-paper-bg)',
                background: 'var(--color-paper-dark)',
                border: 'none',
                borderRadius: '4px',
                padding: '4px 11px',
                cursor: saving ? 'wait' : 'pointer',
              }}
            >
              {saving && (
                <Icon
                  icon="mdi:loading"
                  style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }}
                />
              )}
              Save to My Reviews
            </button>
            {reviewId && (
              <button
                onClick={() => navigate(ROUTES.REVIEW_DETAIL(reviewId))}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontFamily: "'Newsreader', serif",
                  fontSize: '13px',
                  color: 'var(--color-paper-mid)',
                  border: '1px solid var(--color-paper-light)',
                  borderRadius: '4px',
                  padding: '4px 9px',
                  background: 'none',
                  cursor: 'pointer',
                }}
              >
                <Icon icon="mdi:open-in-new" style={{ width: 13, height: 13 }} />
                View in My Reviews
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Body ──────────────────────────────────────────────────────── */}
      {status === 'idle' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '16px 32px 0' }}>
            <UsageExhaustedBanner feature="pdf" />
          </div>
          <PDFUploadZone onFile={upload} disabled={quotaExhausted} />
        </div>
      )}

      {(status === 'uploading' || status === 'streaming') && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
        >
          <div
            style={{
              width: '380px',
              maxWidth: '90vw',
              border: '1px solid var(--color-paper-light)',
              borderRadius: '10px',
              background: 'var(--color-paper-bg)',
              padding: '20px 22px',
              boxShadow: '0 8px 28px rgba(0,0,0,0.06)',
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-inknut)',
                fontSize: '15px',
                fontWeight: 700,
                color: 'var(--color-paper-dark)',
                marginBottom: '14px',
              }}
            >
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
                    <div
                      style={{
                        width: 26,
                        height: 26,
                        borderRadius: '50%',
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background:
                          s.status === 'done'
                            ? 'rgba(31,122,61,0.12)'
                            : 'var(--color-paper-surface)',
                      }}
                    >
                      <Icon
                        icon={STEP_ICONS[s.status]}
                        style={{
                          width: 14,
                          height: 14,
                          color: s.status === 'done' ? '#1f7a3d' : 'var(--color-paper-mid)',
                          animation: s.status === 'running' ? 'spin 1s linear infinite' : 'none',
                        }}
                      />
                    </div>
                    <span
                      style={{
                        fontFamily: "'Newsreader', serif",
                        fontSize: '15px',
                        color:
                          s.status === 'running'
                            ? 'var(--color-paper-dark)'
                            : 'var(--color-paper-mid)',
                        fontWeight: s.status === 'running' ? 600 : 400,
                      }}
                    >
                      {s.label}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
              {steps.length === 0 && (
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 0' }}
                >
                  <div
                    style={{
                      width: 26,
                      height: 26,
                      borderRadius: '50%',
                      flexShrink: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'var(--color-paper-surface)',
                    }}
                  >
                    <Icon
                      icon="mdi:loading"
                      style={{
                        width: 14,
                        height: 14,
                        color: 'var(--color-paper-mid)',
                        animation: 'spin 1s linear infinite',
                      }}
                    />
                  </div>
                  <span
                    style={{
                      fontFamily: "'Newsreader', serif",
                      fontSize: '15px',
                      color: 'var(--color-paper-mid)',
                    }}
                  >
                    Uploading...
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
          }}
        >
          <Icon
            icon="mdi:alert-circle-outline"
            style={{ width: 32, height: 32, color: '#c0392b' }}
          />
          <span
            style={{
              fontFamily: "'Newsreader', serif",
              color: '#c0392b',
              maxWidth: '480px',
              textAlign: 'center',
            }}
          >
            {friendlyError(error, 'Something went wrong while processing this document.')}
          </span>
          <button
            onClick={reset}
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: '15px',
              cursor: 'pointer',
              color: 'var(--color-paper-mid)',
              background: 'none',
              border: '1px solid var(--color-paper-light)',
              borderRadius: '4px',
              padding: '6px 14px',
            }}
          >
            Try again
          </button>
        </div>
      )}

      {(status === 'ready' || status === 'saving') && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            overflow: 'hidden',
          }}
        >
          {isMobile && (
            <div
              style={{
                flexShrink: 0,
                display: 'flex',
                borderBottom: '1px solid rgba(41, 17, 0, 0.08)',
              }}
            >
              {[
                { key: 'editor', label: 'Editor' },
                { key: 'annotations', label: `Annotations (${pendingAnnotations.length})` },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setMobileTab(tab.key)}
                  style={{
                    flex: 1,
                    padding: '12px 8px',
                    minHeight: 44,
                    border: 'none',
                    borderBottom:
                      mobileTab === tab.key
                        ? '2px solid var(--color-paper-dark)'
                        : '2px solid transparent',
                    background: 'none',
                    cursor: 'pointer',
                    fontFamily: "'Newsreader', serif",
                    fontSize: '15px',
                    fontWeight: mobileTab === tab.key ? 600 : 400,
                    color:
                      mobileTab === tab.key ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}

          {/* Left: editor */}
          <div
            style={{
              flex: 1,
              display: !isMobile || mobileTab === 'editor' ? 'flex' : 'none',
              flexDirection: 'column',
              overflow: 'hidden',
              borderRight: isMobile ? 'none' : '1px solid rgba(41, 17, 0, 0.08)',
            }}
          >
            <SelectionToolbar
              selection={selection}
              onExplain={handleExplain}
              onRewrite={handleRewrite}
            />
            <RewritePreview
              result={selectionResult}
              onApply={handleApply}
              onClose={clearSelectionResult}
            />
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
          <div
            style={{
              width: isMobile ? '100%' : '360px',
              flexShrink: 0,
              display: !isMobile || mobileTab === 'annotations' ? 'flex' : 'none',
              flexDirection: 'column',
              overflow: 'hidden',
              background: 'var(--color-paper-surface)',
            }}
          >
            {!isMobile && (
              <div
                style={{
                  flexShrink: 0,
                  padding: '10px 14px',
                  borderBottom: '1px solid rgba(41, 17, 0, 0.08)',
                }}
              >
                <span
                  style={{
                    fontFamily: "'Newsreader', serif",
                    fontSize: '13px',
                    fontWeight: 600,
                    color: 'var(--color-paper-mid)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  Annotations ({pendingAnnotations.length})
                </span>
              </div>
            )}
            <div className="themed-scroll" style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
              {pendingAnnotations.length === 0 ? (
                <div
                  style={{
                    fontFamily: "'Newsreader', serif",
                    fontSize: '15px',
                    color: 'var(--color-paper-mid)',
                    textAlign: 'center',
                    marginTop: '24px',
                  }}
                >
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
                      if (isMobile) setMobileTab('editor');
                    }}
                    onAction={(action) => handleAnnotationAction(a, action)}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PDFAgentPage;

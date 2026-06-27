import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useReviewsStore } from '@/shared/store/useReviewsStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { reviewsApi } from '@/features/reviews/reviewsApi';
import { ROUTES } from '@/shared/constant/routes';
import { useIsMobile } from '@/shared/hooks/useIsMobile';

const token = () => useAuthStore.getState().token;

const relativeDate = (iso) => {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`;
  return new Date(iso).toLocaleDateString();
};

const ReviewCard = ({ review, onDelete, onDuplicate }) => {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e) => { if (!menuRef.current?.contains(e.target)) setMenuOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.2 }}
      style={{
        border: '1px solid var(--color-paper-light)',
        borderRadius: '4px',
        padding: '14px 16px',
        background: 'var(--color-paper-bg)',
        display: 'flex', alignItems: 'center', gap: '12px',
        cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-paper-mid)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-paper-light)')}
      onClick={() => navigate(ROUTES.REVIEW_DETAIL(review.id))}
    >
      <Icon icon="mdi:file-document-outline" style={{ width: 20, height: 20, color: 'var(--color-paper-mid)', flexShrink: 0 }} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: "'Noto Serif', serif", fontSize: '15px', fontWeight: 600, color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {review.title}
        </div>
        <div style={{ fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-light)', marginTop: '2px' }}>
          {relativeDate(review.updated_at)} · {review.query}
        </div>
      </div>

      {/* Action menu */}
      <div style={{ position: 'relative', flexShrink: 0 }} ref={menuRef} onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => setMenuOpen((v) => !v)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-light)', padding: '4px', borderRadius: '4px', display: 'flex', alignItems: 'center' }}
        >
          <Icon icon="mdi:dots-horizontal" style={{ width: 16, height: 16 }} />
        </button>
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.12 }}
              style={{
                position: 'absolute', right: 0, top: '28px',
                background: 'var(--color-paper-bg)',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '4px',
                boxShadow: '0 6px 20px rgba(0,0,0,0.1)',
                minWidth: '148px', zIndex: 100,
                overflow: 'hidden',
              }}
            >
              {[
                { icon: 'mdi:open-in-new', label: 'Open', action: () => navigate(ROUTES.REVIEW_DETAIL(review.id)) },
                { icon: 'mdi:file-code-outline', label: 'Export LaTeX', action: () => reviewsApi.download(token(), review.id, 'tex').catch(() => {}) },
                { icon: 'mdi:language-markdown-outline', label: 'Export Markdown', action: () => reviewsApi.download(token(), review.id, 'markdown').catch(() => {}) },
                { icon: 'mdi:file-pdf-box', label: 'Export PDF', action: () => reviewsApi.download(token(), review.id, 'pdf').catch(() => {}) },
                { icon: 'mdi:folder-zip-outline', label: 'Export ZIP', action: () => reviewsApi.download(token(), review.id, 'zip').catch(() => {}) },
                { icon: 'mdi:content-copy', label: 'Duplicate', action: () => { onDuplicate(review.id); setMenuOpen(false); } },
                { icon: 'mdi:delete-outline', label: 'Delete', action: () => { onDelete(review.id); setMenuOpen(false); }, danger: true },
              ].map(({ icon, label, action, danger }) => (
                <button
                  key={label}
                  onClick={() => { action(); setMenuOpen(false); }}
                  style={{
                    width: '100%', textAlign: 'left', padding: '8px 12px',
                    background: 'none', border: 'none', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '8px',
                    fontFamily: "'Noto Serif', serif", fontSize: '13px',
                    color: danger ? '#c0392b' : 'var(--color-paper-dark)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-paper-surface)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                >
                  <Icon icon={icon} style={{ width: 14, height: 14 }} />
                  {label}
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
};

const MyReviewsPage = () => {
  const navigate = useNavigate();
  const isMobile = useIsMobile(480);
  const { items, pagination, search, listLoading, listError, fetchList, loadMore, setSearch, deleteReview, duplicateReview } = useReviewsStore();
  const [searchInput, setSearchInput] = useState(search);
  const debounceRef = useRef(null);

  useEffect(() => { fetchList(1); }, [fetchList]);

  const handleSearch = (val) => {
    setSearchInput(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearch(val);
      fetchList(1);
    }, 350);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this review?')) return;
    await deleteReview(id);
  };

  const handleDuplicate = async (id) => {
    await duplicateReview(id);
  };

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '20px 14px' : '32px 24px' }}>
      <div style={{ maxWidth: '640px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <button
            onClick={() => navigate(-1)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-mid)', padding: 0, display: 'flex', alignItems: 'center' }}
          >
            <Icon icon="mdi:arrow-left" style={{ width: 18, height: 18 }} />
          </button>
          <h1 style={{ fontFamily: "'Noto Serif', serif", fontSize: '20px', fontWeight: 700, color: 'var(--color-paper-dark)', margin: 0 }}>
            My Reviews
          </h1>
          <span style={{ fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-light)', marginLeft: 'auto' }}>
            {pagination.total} review{pagination.total !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Search */}
        <div style={{ position: 'relative', marginBottom: '16px' }}>
          <Icon icon="mdi:magnify" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', width: 16, height: 16, color: 'var(--color-paper-light)' }} />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search by name..."
            style={{
              width: '100%', boxSizing: 'border-box',
              paddingLeft: '34px', paddingRight: '12px', paddingTop: '8px', paddingBottom: '8px',
              border: '1px solid var(--color-paper-light)',
              borderRadius: '4px',
              background: 'var(--color-paper-surface)',
              fontFamily: "'Noto Serif', serif", fontSize: '14px',
              color: 'var(--color-paper-dark)',
              outline: 'none',
            }}
          />
        </div>

        {/* List */}
        {listError && (
          <div style={{ fontFamily: "'Noto Serif', serif", fontSize: '14px', color: '#c0392b', padding: '12px', marginBottom: '12px' }}>
            {listError}
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <AnimatePresence initial={false}>
            {items.map((r) => (
              <ReviewCard key={r.id} review={r} onDelete={handleDelete} onDuplicate={handleDuplicate} />
            ))}
          </AnimatePresence>
        </div>

        {/* Empty state */}
        {!listLoading && items.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-paper-light)', fontFamily: "'Noto Serif', serif", fontSize: '15px' }}>
            {search ? 'No reviews found.' : 'No reviews yet. Create a Literature Review to get started!'}
          </div>
        )}

        {/* Load more */}
        {pagination.has_more && (
          <button
            onClick={loadMore}
            disabled={listLoading}
            style={{
              width: '100%', marginTop: '16px', padding: '10px',
              border: '1px solid var(--color-paper-light)',
              borderRadius: '4px',
              background: 'none', cursor: listLoading ? 'wait' : 'pointer',
              fontFamily: "'Noto Serif', serif", fontSize: '13px',
              color: 'var(--color-paper-mid)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
            }}
          >
            {listLoading
              ? <><Icon icon="mdi:loading" style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} /> Loading...</>
              : 'Load more'
            }
          </button>
        )}

        {/* Loading spinner (first page) */}
        {listLoading && items.length === 0 && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '32px' }}>
            <Icon icon="mdi:loading" style={{ width: 24, height: 24, color: 'var(--color-paper-light)', animation: 'spin 1s linear infinite' }} />
          </div>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default MyReviewsPage;

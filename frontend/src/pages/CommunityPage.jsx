import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useCommunityStore } from '@/shared/store/useCommunityStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { reviewsApi } from '@/features/reviews/reviewsApi';
import { ROUTES } from '@/shared/constant/routes';
import SiteHeader from '@/shared/components/layout/SiteHeader';
import SiteFooter from '@/shared/components/layout/SiteFooter';
import { showError } from '@/shared/utils/toast';
import { friendlyError } from '@/shared/utils/errorMessage';

const relativeDate = (iso) => {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`;
  return new Date(iso).toLocaleDateString();
};

const getInitials = (name) =>
  name ? name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase() : '?';

const mdComponents = {
  h1: ({ children }) => <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-paper-dark)', margin: '8px 0 4px' }}>{children}</h3>,
  h2: ({ children }) => <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-paper-dark)', margin: '8px 0 4px' }}>{children}</h3>,
  p: ({ children }) => <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--color-paper-dark)', margin: '0 0 8px' }}>{children}</p>,
  ul: ({ children }) => <ul style={{ margin: '4px 0 8px', paddingLeft: 18 }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ margin: '4px 0 8px', paddingLeft: 18 }}>{children}</ol>,
  li: ({ children }) => <li style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--color-paper-dark)' }}>{children}</li>,
  code: ({ children }) => <code style={{ fontSize: 12, background: 'var(--color-paper-surface)', padding: '1px 5px', borderRadius: 3 }}>{children}</code>,
};

// ── Submit modal ──────────────────────────────────────────────────────────────
const SubmitModal = ({ onClose, modalRef }) => {
  const token = useAuthStore((s) => s.token);
  const submit = useCommunityStore((s) => s.submit);
  const submitLoading = useCommunityStore((s) => s.submitLoading);
  const submitError = useCommunityStore((s) => s.submitError);

  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [reviewId, setReviewId] = useState('');
  const [myReviews, setMyReviews] = useState([]);
  const [done, setDone] = useState(false);

  useEffect(() => {
    reviewsApi.list(token, { limit: 50 }).then((d) => setMyReviews(d.data)).catch((e) => showError(e, "Couldn't load your reviews."));
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    try {
      await submit({ title: title.trim(), content: content.trim(), review_id: reviewId || null });
      setDone(true);
    } catch {
      // submitError already set by the store
    }
  };

  return (
    <motion.div
      ref={modalRef}
      initial={{ opacity: 0, scale: 0.96, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96, y: 8 }}
      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
      style={{
        background: 'var(--color-paper-bg)', border: '1px solid var(--color-paper-light)',
        borderRadius: 12, boxShadow: '0 8px 40px rgba(0,0,0,0.2)',
        width: 480, maxWidth: '90vw', padding: 20,
      }}
    >
      {done ? (
        <div style={{ textAlign: 'center', padding: '24px 8px' }}>
          <Icon icon="mdi:check-circle-outline" style={{ fontSize: 36, color: 'var(--color-paper-mid)' }} />
          <p style={{ fontFamily: "'Noto Serif', serif", fontSize: 15, color: 'var(--color-paper-dark)', margin: '12px 0 20px' }}>
            Your contribution is awaiting admin approval
          </p>
          <button onClick={onClose} style={{
            padding: '8px 20px', borderRadius: 999, border: 'none',
            background: 'var(--color-paper-dark)', color: 'var(--color-paper-bg)',
            fontFamily: "'Noto Serif', serif", fontSize: 14, cursor: 'pointer',
          }}>
            Close
          </button>
        </div>
      ) : (
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h3 style={{ fontFamily: 'var(--font-inknut)', fontSize: 17, color: 'var(--color-paper-dark)', margin: 0 }}>Contribute</h3>
            <button type="button" onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-mid)' }}>
              <Icon icon="mdi:close" style={{ fontSize: 18 }} />
            </button>
          </div>

          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title"
            required
            style={{
              width: '100%', boxSizing: 'border-box', padding: '9px 12px', marginBottom: 10,
              border: '1px solid var(--color-paper-light)', borderRadius: 6,
              fontFamily: "'Noto Serif', serif", fontSize: 14, color: 'var(--color-paper-dark)',
              background: 'var(--color-paper-surface)', outline: 'none',
            }}
          />

          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Content (Markdown supported)..."
            required
            rows={6}
            style={{
              width: '100%', boxSizing: 'border-box', padding: '9px 12px', marginBottom: 10,
              border: '1px solid var(--color-paper-light)', borderRadius: 6,
              fontFamily: "'Noto Serif', serif", fontSize: 14, color: 'var(--color-paper-dark)',
              background: 'var(--color-paper-surface)', outline: 'none', resize: 'vertical',
            }}
          />

          {myReviews.length > 0 && (
            <select
              value={reviewId}
              onChange={(e) => setReviewId(e.target.value)}
              style={{
                width: '100%', boxSizing: 'border-box', padding: '9px 12px', marginBottom: 14,
                border: '1px solid var(--color-paper-light)', borderRadius: 6,
                fontFamily: "'Noto Serif', serif", fontSize: 13, color: 'var(--color-paper-mid)',
                background: 'var(--color-paper-surface)',
              }}
            >
              <option value="">(No linked review)</option>
              {myReviews.map((r) => (
                <option key={r.id} value={r.id}>{r.title}</option>
              ))}
            </select>
          )}

          {submitError && (
            <p style={{ fontFamily: "'Noto Serif', serif", fontSize: 13, color: '#c0392b', margin: '0 0 10px' }}>{friendlyError(submitError, "Couldn't submit your contribution — please try again.")}</p>
          )}

          <button
            type="submit"
            disabled={submitLoading}
            style={{
              width: '100%', padding: '10px 0', borderRadius: 999, border: 'none',
              background: 'var(--color-paper-dark)', color: 'var(--color-paper-bg)',
              fontFamily: "'Noto Serif', serif", fontSize: 15, cursor: submitLoading ? 'wait' : 'pointer',
            }}
          >
            {submitLoading ? 'Submitting...' : 'Submit contribution'}
          </button>
        </form>
      )}
    </motion.div>
  );
};

// ── Contribution card ─────────────────────────────────────────────────────────
const ContributionCard = ({ contribution, onVote, isAuthenticated, isOwn }) => (
  <motion.div
    initial={{ opacity: 0, y: 6 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -4 }}
    transition={{ duration: 0.2 }}
    style={{
      border: '1px solid var(--color-paper-light)', borderRadius: 8,
      padding: '16px 18px', background: 'var(--color-paper-bg)',
      display: 'flex', gap: 14,
    }}
  >
    {/* Vote button */}
    <button
      onClick={() => onVote(contribution.id)}
      disabled={!isAuthenticated || isOwn}
      title={!isAuthenticated ? 'Log in to vote' : isOwn ? 'You cannot vote on your own contribution' : 'Vote'}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
        background: contribution.voted_by_me ? 'var(--color-brand-50)' : 'var(--color-paper-surface)',
        border: contribution.voted_by_me ? '1px solid var(--color-brand-500)' : '1px solid var(--color-paper-light)',
        borderRadius: 8, padding: '8px 10px', height: 'fit-content',
        cursor: (!isAuthenticated || isOwn) ? 'not-allowed' : 'pointer',
        opacity: (!isAuthenticated || isOwn) ? 0.5 : 1,
        flexShrink: 0,
      }}
    >
      <Icon icon="mdi:arrow-up-bold" style={{ fontSize: 16, color: contribution.voted_by_me ? 'var(--color-brand-500)' : 'var(--color-paper-mid)' }} />
      <span style={{ fontSize: 13, fontWeight: 700, color: contribution.voted_by_me ? 'var(--color-brand-600)' : 'var(--color-paper-dark)' }}>
        {contribution.total_votes}
      </span>
    </button>

    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
        <h3 style={{ fontFamily: 'var(--font-inknut)', fontSize: 16, fontWeight: 500, color: 'var(--color-paper-dark)', margin: 0 }}>
          {contribution.title}
        </h3>
        <span style={{ fontSize: 12, color: 'var(--color-paper-light)' }}>
          {contribution.author_name || 'Anonymous'} · {relativeDate(contribution.created_at)}
        </span>
      </div>
      <div style={{ fontSize: 14 }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
          {contribution.content}
        </ReactMarkdown>
      </div>
    </div>
  </motion.div>
);

// ── Leaderboard panel ─────────────────────────────────────────────────────────
const LeaderboardPanel = ({ rows, loading }) => (
  <div style={{
    border: '1px solid var(--color-paper-light)', borderRadius: 8,
    padding: '16px 18px', background: 'var(--color-paper-bg)',
  }}>
    <h3 style={{ fontFamily: 'var(--font-inknut)', fontSize: 15, fontWeight: 500, color: 'var(--color-paper-dark)', margin: '0 0 14px' }}>
      🏆 Leaderboard
    </h3>
    {loading && <Icon icon="mdi:loading" style={{ fontSize: 18, color: 'var(--color-paper-light)' }} />}
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {rows.map((row, i) => (
        <div key={row.user_id} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--font-inknut)', fontSize: 13, color: 'var(--color-paper-light)', width: 20, flexShrink: 0 }}>
            #{i + 1}
          </span>
          <div style={{
            width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
            background: 'var(--color-brand-100)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700, color: 'var(--color-brand-600)', overflow: 'hidden',
          }}>
            {row.avatar_url ? <img src={row.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : getInitials(row.full_name)}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {row.full_name || 'Anonymous'}
            </div>
            <div style={{ fontSize: 11, color: 'var(--color-paper-light)' }}>
              {row.contributions_count} contributions
            </div>
          </div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-paper-mid)', flexShrink: 0 }}>
            {row.total_votes}
          </span>
        </div>
      ))}
      {!loading && rows.length === 0 && (
        <p style={{ fontSize: 13, color: 'var(--color-paper-light)', margin: 0 }}>No data yet.</p>
      )}
    </div>
  </div>
);

// ── Page ──────────────────────────────────────────────────────────────────────
const CommunityPage = () => {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);

  const { items, pagination, sort, listLoading, listError, fetchList, loadMore, setSort, toggleVote, leaderboard, leaderboardLoading, fetchLeaderboard } = useCommunityStore();

  const [modalOpen, setModalOpen] = useState(false);
  const modalRef = useRef(null);

  useEffect(() => { fetchList(1); fetchLeaderboard(); }, [fetchList, fetchLeaderboard]);

  useEffect(() => {
    if (!modalOpen) return;
    const handler = (e) => { if (!modalRef.current?.contains(e.target)) setModalOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [modalOpen]);

  const handleContribute = () => {
    if (!isAuthenticated) { navigate(ROUTES.LOGIN); return; }
    setModalOpen(true);
  };

  const handleVote = (id) => {
    if (!isAuthenticated) { navigate(ROUTES.LOGIN); return; }
    toggleVote(id).catch((e) => showError(e, "Couldn't register your vote — please try again."));
  };

  return (
    <div style={{ fontFamily: "'Noto Serif', serif", background: 'var(--color-paper-bg)', minHeight: '100vh' }}>
      <SiteHeader />

      <div style={{ padding: '32px 24px 60px', paddingTop: 89 }}>
      <div style={{ maxWidth: 920, margin: '0 auto' }}>
        {/* Page title */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <h1 style={{ fontFamily: 'var(--font-inknut)', fontSize: 40, fontWeight: 500, color: 'var(--color-paper-dark)', margin: 0 }}>
            Built Together
          </h1>
          <p style={{ fontFamily: "'Noto Serif', serif", fontSize: 15, color: 'var(--color-paper-mid)', margin: '8px 0 0' }}>
            Contribute, vote, and help build PaperPulse together.
          </p>
        </div>

        {/* Contribute CTA */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
          <button
            onClick={handleContribute}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '10px 20px', borderRadius: 999, border: 'none',
              background: 'var(--color-paper-dark)', color: 'var(--color-paper-bg)',
              fontFamily: "'Noto Serif', serif", fontSize: 15, cursor: 'pointer',
            }}
          >
            <Icon icon="mdi:plus" style={{ fontSize: 16 }} />
            Contribute
          </button>
        </div>

        {/* Sort toggle */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 18 }}>
          {[['new', 'Newest'], ['top', 'Top']].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSort(key)}
              style={{
                padding: '6px 16px', borderRadius: 999, cursor: 'pointer',
                border: sort === key ? '1px solid var(--color-brand-500)' : '1px solid var(--color-paper-light)',
                background: sort === key ? 'var(--color-brand-50)' : 'transparent',
                color: sort === key ? 'var(--color-brand-600)' : 'var(--color-paper-mid)',
                fontFamily: "'Noto Serif', serif", fontSize: 14, fontWeight: sort === key ? 600 : 400,
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Two-column layout */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 24, alignItems: 'start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {listError && <p style={{ fontFamily: "'Noto Serif', serif", fontSize: 14, color: '#c0392b' }}>{friendlyError(listError, "Couldn't load contributions.")}</p>}

            <AnimatePresence initial={false}>
              {items.map((c) => (
                <ContributionCard
                  key={c.id}
                  contribution={c}
                  onVote={handleVote}
                  isAuthenticated={isAuthenticated}
                  isOwn={user?.id === c.user_id}
                />
              ))}
            </AnimatePresence>

            {!listLoading && items.length === 0 && (
              <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-paper-light)', fontFamily: "'Noto Serif', serif", fontSize: 15 }}>
                No contributions have been approved yet.
              </div>
            )}

            {pagination.has_more && (
              <button
                onClick={loadMore}
                disabled={listLoading}
                style={{
                  padding: '10px', border: '1px solid var(--color-paper-light)', borderRadius: 6,
                  background: 'none', cursor: listLoading ? 'wait' : 'pointer',
                  fontFamily: "'Noto Serif', serif", fontSize: 13, color: 'var(--color-paper-mid)',
                }}
              >
                {listLoading ? 'Loading...' : 'Load more'}
              </button>
            )}
          </div>

          <LeaderboardPanel rows={leaderboard} loading={leaderboardLoading} />
        </div>
      </div>
      </div>

      <SiteFooter />

      {createPortal(
        <AnimatePresence>
          {modalOpen && (
            <div style={{
              position: 'fixed', inset: 0, zIndex: 9999,
              background: 'rgba(0,0,0,0.35)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <SubmitModal onClose={() => setModalOpen(false)} modalRef={modalRef} />
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}

    </div>
  );
};

export default CommunityPage;

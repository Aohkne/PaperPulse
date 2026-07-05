import { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { adminApi } from '@/features/admin/adminApi';

const TABS = [
  ['pending', 'Pending'],
  ['approved', 'Approved'],
  ['rejected', 'Rejected'],
  ['', 'All'],
];

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function StatusBadge({ status }) {
  const colors = {
    pending: { bg: '#fff3cd', text: '#8a6d00', border: '#f0dca0' },
    approved: {
      bg: 'var(--color-admin-role-bg)',
      text: 'var(--color-admin-mid)',
      border: 'var(--color-admin-border)',
    },
    rejected: { bg: '#fed7d7', text: '#c0392b', border: '#e8a8a8' },
  };
  const c = colors[status] || colors.pending;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: 20,
        fontSize: 11,
        fontWeight: 600,
        textTransform: 'capitalize',
        background: c.bg,
        color: c.text,
        border: `1px solid ${c.border}`,
      }}
    >
      {status}
    </span>
  );
}

function ContributionRow({ c, onApprove, onReject }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      style={{
        border: '1px solid var(--color-admin-border)',
        borderRadius: 10,
        padding: '14px 16px',
        background: 'var(--color-admin-surface)',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 6,
          flexWrap: 'wrap',
        }}
      >
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-admin-text)', margin: 0 }}>
          {c.title}
        </h3>
        <StatusBadge status={c.status} />
        <span style={{ fontSize: 12, color: 'var(--color-admin-mid)' }}>
          {c.author_name || 'Anonymous'} · {fmtDate(c.created_at)}
        </span>
        {c.status === 'approved' && (
          <span style={{ fontSize: 12, color: 'var(--color-admin-mid)' }}>
            · {c.total_votes} votes
          </span>
        )}
      </div>

      <p
        style={{
          fontSize: 13,
          color: 'var(--color-admin-mid)',
          margin: '0 0 10px',
          whiteSpace: 'pre-wrap',
          maxHeight: 80,
          overflow: 'hidden',
        }}
      >
        {c.content}
      </p>

      {c.status === 'rejected' && c.rejection_reason && (
        <p style={{ fontSize: 12, color: '#c0392b', margin: '0 0 10px' }}>
          Rejection reason: {c.rejection_reason}
        </p>
      )}

      {c.status === 'pending' && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => onApprove(c.id)}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              border: 'none',
              cursor: 'pointer',
              background: 'var(--color-admin-accent)',
              color: '#fff',
              fontSize: 12,
              fontWeight: 500,
            }}
          >
            Approve
          </button>
          <button
            onClick={() => onReject(c.id)}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              cursor: 'pointer',
              border: '1px solid #e8a8a8',
              background: '#fff5f5',
              color: '#c0392b',
              fontSize: 12,
            }}
          >
            Reject
          </button>
        </div>
      )}
    </motion.div>
  );
}

export default function CommunityModerationPage() {
  const token = useAuthStore((s) => s.token);
  const [status, setStatus] = useState('pending');
  const [data, setData] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchQueue = useCallback(
    (s) => {
      if (!token) {
        return Promise.resolve(null);
      }
      return adminApi.getContributions(token, { status: s || undefined, limit: 50 });
    },
    [token]
  );

  useEffect(() => {
    let cancelled = false;

    void fetchQueue(status)
      .then((res) => {
        if (cancelled || !res) {
          return;
        }
        setData(res.data ?? []);
        setTotal(res.pagination?.total ?? 0);
        setLoading(false);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        console.error(error);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status, fetchQueue]);

  const handleApprove = async (id) => {
    setLoading(true);
    await adminApi.approveContribution(token, id);
    const res = await fetchQueue(status);
    if (!res) {
      setLoading(false);
      return;
    }
    setData(res.data ?? []);
    setTotal(res.pagination?.total ?? 0);
    setLoading(false);
  };

  const handleReject = async (id) => {
    const reason = window.prompt('Reason for rejecting this contribution:');
    if (!reason) return;
    setLoading(true);
    await adminApi.rejectContribution(token, id, reason);
    const res = await fetchQueue(status);
    if (!res) {
      setLoading(false);
      return;
    }
    setData(res.data ?? []);
    setTotal(res.pagination?.total ?? 0);
    setLoading(false);
  };

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 28 }}
        style={{ marginBottom: 24 }}
      >
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: 'var(--color-admin-text)' }}>
          Community Moderation
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-admin-mid)' }}>
          {total} contribution{total !== 1 ? 's' : ''} {status ? `· ${status}` : ''}
        </p>
      </motion.div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {TABS.map(([key, label]) => (
          <button
            key={key || 'all'}
            onClick={() => {
              setLoading(true);
              setStatus(key);
            }}
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              border: '1px solid',
              borderColor:
                status === key ? 'var(--color-admin-accent)' : 'var(--color-admin-border)',
              background: status === key ? 'var(--color-admin-accent-bg)' : 'transparent',
              color: status === key ? 'var(--color-admin-accent-text)' : 'var(--color-admin-mid)',
              fontSize: 12,
              fontWeight: status === key ? 600 : 400,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-admin-mid)' }}>
          <Icon icon="mdi:loading" style={{ fontSize: 24, animation: 'spin 1s linear infinite' }} />
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <AnimatePresence initial={false}>
            {data.map((c) => (
              <ContributionRow key={c.id} c={c} onApprove={handleApprove} onReject={handleReject} />
            ))}
          </AnimatePresence>
          {data.length === 0 && (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--color-admin-mid)' }}>
              No contributions found
            </div>
          )}
        </div>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

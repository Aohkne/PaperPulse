import { useEffect, useState, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import {
  useReactTable, getCoreRowModel, flexRender,
} from '@tanstack/react-table';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { adminApi } from '@/features/admin/adminApi';
import { showError, showSuccess } from '@/shared/utils/toast';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
}

function TierBadge({ tier }) {
  const colors = {
    free: { bg: 'var(--color-admin-role-bg)', fg: 'var(--color-admin-mid)', border: 'var(--color-admin-border)' },
    plus: { bg: 'rgba(59,130,246,0.12)', fg: '#3b82f6', border: 'rgba(59,130,246,0.3)' },
    unlimited: { bg: 'var(--color-admin-accent-bg)', fg: 'var(--color-admin-accent-text)', border: 'var(--color-admin-role-border)' },
  };
  const c = colors[tier] ?? colors.free;
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 20,
      fontSize: 11, fontWeight: 600, textTransform: 'capitalize',
      background: c.bg, color: c.fg, border: `1px solid ${c.border}`,
    }}>
      {tier}
    </span>
  );
}

function QuotaCell({ quota, topup, used }) {
  return (
    <div style={{ fontSize: 12, lineHeight: 1.5 }}>
      <div style={{ color: 'var(--color-admin-text)' }}>
        {quota === null ? '∞' : quota} sub <span style={{ color: 'var(--color-admin-muted)' }}>+ {topup} top-up</span>
      </div>
      <div style={{ color: 'var(--color-admin-muted)' }}>{used} used this period</div>
    </div>
  );
}

// ── Top-up modal ──────────────────────────────────────────────────────────────

function TopupModal({ account, onClose, onSubmit }) {
  const [amounts, setAmounts] = useState({ lr: 0, pdf: 0, gap: 0 });
  const [submitting, setSubmitting] = useState(false);

  const setField = (key) => (e) => {
    const v = parseInt(e.target.value, 10);
    setAmounts((a) => ({ ...a, [key]: Number.isNaN(v) ? 0 : v }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!amounts.lr && !amounts.pdf && !amounts.gap) {
      showError('Enter at least one non-zero amount.');
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(amounts);
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  const FIELDS = [
    { key: 'lr', label: 'Literature Review' },
    { key: 'pdf', label: 'PDF Agent' },
    { key: 'gap', label: 'Research Gap' },
  ];

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
        style={{
          background: 'var(--color-admin-surface)', border: '1px solid var(--color-admin-border)',
          borderRadius: 12, padding: 22, width: 360, maxWidth: '90vw',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ margin: '0 0 4px', fontSize: 16, fontWeight: 700, color: 'var(--color-admin-text)' }}>
          Top up usage
        </h3>
        <p style={{ margin: '0 0 16px', fontSize: 12, color: 'var(--color-admin-mid)' }}>
          {account.email}
        </p>

        <form onSubmit={handleSubmit}>
          {FIELDS.map(({ key, label }) => (
            <div key={key} style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--color-admin-mid)', marginBottom: 4 }}>
                {label}
              </label>
              <input
                type="number"
                value={amounts[key]}
                onChange={setField(key)}
                style={{
                  width: '100%', boxSizing: 'border-box', padding: '8px 10px',
                  border: '1px solid var(--color-admin-border)', borderRadius: 6,
                  background: 'var(--color-admin-input-bg)', color: 'var(--color-admin-text)',
                  fontSize: 13, outline: 'none',
                }}
              />
            </div>
          ))}

          <div style={{ display: 'flex', gap: 8, marginTop: 18 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                flex: 1, padding: '9px 0', borderRadius: 8, fontSize: 13, cursor: 'pointer',
                border: '1px solid var(--color-admin-border)', background: 'transparent', color: 'var(--color-admin-mid)',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                flex: 1, padding: '9px 0', borderRadius: 8, fontSize: 13, fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer', border: 'none',
                background: 'var(--color-admin-accent)', color: '#fff', opacity: submitting ? 0.7 : 1,
              }}
            >
              {submitting ? 'Saving…' : 'Top up'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

// ── table columns ─────────────────────────────────────────────────────────────

function buildColumns(onReset, onTopup) {
  return [
    { accessorKey: 'email', header: 'Email', size: 220 },
    {
      accessorKey: 'tier',
      header: 'Tier',
      size: 90,
      cell: ({ getValue }) => <TierBadge tier={getValue()} />,
    },
    {
      id: 'lr',
      header: 'Literature Review',
      size: 150,
      cell: ({ row }) => (
        <QuotaCell
          quota={row.original.subscription_lr_quota}
          topup={row.original.topup_lr_balance}
          used={row.original.lr_used_this_period}
        />
      ),
    },
    {
      id: 'pdf',
      header: 'PDF Agent',
      size: 150,
      cell: ({ row }) => (
        <QuotaCell
          quota={row.original.subscription_pdf_quota}
          topup={row.original.topup_pdf_balance}
          used={row.original.pdf_used_this_period}
        />
      ),
    },
    {
      id: 'gap',
      header: 'Research Gap',
      size: 150,
      cell: ({ row }) => (
        <QuotaCell
          quota={row.original.subscription_gap_quota}
          topup={row.original.topup_gap_balance}
          used={row.original.gap_used_this_period}
        />
      ),
    },
    {
      accessorKey: 'tier_period_end',
      header: 'Period Ends',
      size: 100,
      cell: ({ getValue }) => fmtDate(getValue()),
    },
    {
      id: 'actions',
      header: 'Actions',
      size: 150,
      cell: ({ row }) => {
        const a = row.original;
        return (
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={() => onReset(a)} style={actionBtnStyle()}>Reset</button>
            <button onClick={() => onTopup(a)} style={actionBtnStyle(true)}>Top up</button>
          </div>
        );
      },
    },
  ];
}

function actionBtnStyle(accent = false) {
  return {
    padding: '4px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
    border: `1px solid ${accent ? 'var(--color-admin-accent)' : 'var(--color-admin-border)'}`,
    background: accent ? 'var(--color-admin-accent-bg)' : 'var(--color-admin-surface)',
    color: accent ? 'var(--color-admin-accent-text)' : 'var(--color-admin-mid)',
  };
}

// ── sub-components ────────────────────────────────────────────────────────────

function UsageTable({ data, onReset, onTopup }) {
  const columns = useMemo(() => buildColumns(onReset, onTopup), [onReset, onTopup]);
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div style={{ overflowX: 'auto', borderRadius: 10, border: '1px solid var(--color-admin-border)' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id} style={{ background: 'var(--color-admin-bg)' }}>
              {hg.headers.map(h => (
                <th key={h.id} style={{
                  padding: '10px 14px', textAlign: 'left', fontWeight: 600,
                  color: 'var(--color-admin-mid)', fontSize: 12, whiteSpace: 'nowrap',
                  borderBottom: '1px solid var(--color-admin-border)',
                }}>
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          <AnimatePresence mode="popLayout">
            {table.getRowModel().rows.map((row, i) => (
              <motion.tr
                key={row.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ delay: i * 0.025 }}
                style={{ borderBottom: '1px solid var(--color-admin-border)' }}
              >
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} style={{ padding: '11px 14px', color: 'var(--color-admin-text)' }}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </motion.tr>
            ))}
          </AnimatePresence>
          {table.getRowModel().rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} style={{ padding: '32px', textAlign: 'center', color: 'var(--color-admin-mid)' }}>
                No accounts found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function Pagination({ page, hasMore, total, limit, onPage }) {
  const totalPages = Math.ceil(total / limit) || 1;
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16, fontSize: 13 }}>
      <span style={{ color: 'var(--color-admin-mid)' }}>
        Page {page} of {totalPages} · {total} accounts
      </span>
      <div style={{ display: 'flex', gap: 8 }}>
        <PageBtn icon="mdi:chevron-left"  onClick={() => onPage(page - 1)} disabled={page <= 1}  />
        <PageBtn icon="mdi:chevron-right" onClick={() => onPage(page + 1)} disabled={!hasMore}   />
      </div>
    </div>
  );
}

function PageBtn({ icon, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        width: 32, height: 32,
        border: '1px solid var(--color-admin-border)',
        borderRadius: 6,
        background: disabled ? 'transparent' : 'var(--color-admin-surface)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: disabled ? 'var(--color-admin-muted)' : 'var(--color-admin-mid)',
        transition: 'all 0.15s',
      }}
    >
      <Icon icon={icon} style={{ fontSize: 16 }} />
    </button>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const LIMIT = 10;

export default function UsageManagementPage() {
  const token = useAuthStore((s) => s.token);
  const [data,        setData]        = useState([]);
  const [total,       setTotal]       = useState(0);
  const [page,        setPage]        = useState(1);
  const [hasMore,     setHasMore]     = useState(false);
  const [search,      setSearch]      = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [loading,     setLoading]     = useState(true);
  const [topupTarget, setTopupTarget] = useState(null);

  const [prevQuery, setPrevQuery] = useState([page, search]);
  if (page !== prevQuery[0] || search !== prevQuery[1]) {
    setPrevQuery([page, search]);
    if (token) setLoading(true);
  }

  const fetchAccounts = useCallback((p, s) => {
    if (!token) return;
    adminApi
      .getBillingAccounts(token, { page: p, limit: LIMIT, search: s })
      .then(res => {
        setData(res.data ?? []);
        setTotal(res.total ?? 0);
        setHasMore(res.has_more ?? false);
      })
      .catch((e) => showError(e, "Couldn't load usage accounts — please try again."))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { fetchAccounts(page, search); }, [page, search, fetchAccounts]);

  const handleSearch = (e) => { e.preventDefault(); setPage(1); setSearch(searchInput); };

  const handleReset = async (account) => {
    if (!window.confirm(`Reset usage for ${account.email} to their tier's default allowance?`)) return;
    try {
      await adminApi.resetUsage(token, account.user_id);
      showSuccess('Usage reset.');
      fetchAccounts(page, search);
    } catch (e) {
      showError(e, "Couldn't reset usage — please try again.");
    }
  };

  const handleTopup = async (amounts) => {
    try {
      await adminApi.topupUsage(token, topupTarget.user_id, amounts);
      showSuccess('Top-up applied.');
      fetchAccounts(page, search);
    } catch (e) {
      showError(e, "Couldn't apply top-up — please try again.");
      throw e;
    }
  };

  return (
    <div>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 28 }}
        style={{ marginBottom: 24 }}
      >
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: 'var(--color-admin-text)' }}>
          Usage Management
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-admin-mid)' }}>
          {total} billing accounts — reset or top up quota per user
        </p>
      </motion.div>

      {/* Search */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        style={{ marginBottom: 16 }}
      >
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 6, maxWidth: 320 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Icon
              icon="mdi:magnify"
              style={{
                position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                color: 'var(--color-admin-muted)', fontSize: 16, pointerEvents: 'none',
              }}
            />
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="Search by email…"
              style={{
                width: '100%', padding: '8px 10px 8px 32px',
                border: '1px solid var(--color-admin-border)',
                borderRadius: 8,
                background: 'var(--color-admin-input-bg)',
                color: 'var(--color-admin-text)',
                fontSize: 13, outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
          <button
            type="submit"
            style={{
              padding: '8px 14px', borderRadius: 8, border: 'none',
              background: 'var(--color-admin-accent)',
              color: '#fff', fontSize: 13, cursor: 'pointer', fontWeight: 500,
            }}
          >
            Search
          </button>
        </form>
      </motion.div>

      {/* Table */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.12 }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-admin-mid)' }}>
            <Icon icon="mdi:loading" style={{ fontSize: 24, animation: 'spin 1s linear infinite' }} />
          </div>
        ) : (
          <UsageTable data={data} onReset={handleReset} onTopup={setTopupTarget} />
        )}

        <Pagination page={page} hasMore={hasMore} total={total} limit={LIMIT} onPage={setPage} />
      </motion.div>

      {createPortal(
        <AnimatePresence>
          {topupTarget && (
            <TopupModal
              account={topupTarget}
              onClose={() => setTopupTarget(null)}
              onSubmit={handleTopup}
            />
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}

import { useEffect, useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { adminApi } from '@/features/admin/adminApi';
import { showError, showSuccess } from '@/shared/utils/toast';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function TierBadge({ tier }) {
  const colors = {
    free: {
      bg: 'var(--color-admin-role-bg)',
      fg: 'var(--color-admin-mid)',
      border: 'var(--color-admin-border)',
    },
    plus: { bg: 'rgba(59,130,246,0.12)', fg: '#3b82f6', border: 'rgba(59,130,246,0.3)' },
    unlimited: {
      bg: 'var(--color-admin-accent-bg)',
      fg: 'var(--color-admin-accent-text)',
      border: 'var(--color-admin-role-border)',
    },
  };
  const c = colors[tier] ?? colors.free;
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
        color: c.fg,
        border: `1px solid ${c.border}`,
      }}
    >
      {tier}
    </span>
  );
}

function CreditCell({ balance, used }) {
  const unlimited = balance === null || balance === undefined;
  const usedN = Number(used || 0);
  const total = unlimited ? null : Math.max(0, Number(balance)) + usedN;
  const pct = total ? Math.min(100, Math.round((usedN / total) * 100)) : 0;
  return (
    <div style={{ fontSize: 12, lineHeight: 1.5 }}>
      <div style={{ color: 'var(--color-admin-text)' }}>
        {unlimited
          ? '∞ credits'
          : `${Math.max(0, Number(balance)).toFixed(1)} / ${total.toFixed(0)} left`}
      </div>
      <div style={{ color: 'var(--color-admin-muted)' }}>
        {unlimited ? `${usedN.toFixed(1)} used this period` : `${pct}% of monthly budget used`}
      </div>
    </div>
  );
}

// ── table columns ─────────────────────────────────────────────────────────────

function buildColumns(onReset) {
  return [
    { accessorKey: 'email', header: 'Email', size: 240 },
    {
      accessorKey: 'tier',
      header: 'Tier',
      size: 90,
      cell: ({ getValue }) => <TierBadge tier={getValue()} />,
    },
    {
      id: 'credit',
      header: 'Credit pool (shared)',
      size: 200,
      cell: ({ row }) => (
        <CreditCell
          balance={row.original.subscription_credit_balance}
          used={row.original.credit_used_this_period}
        />
      ),
    },
    {
      accessorKey: 'tier_period_end',
      header: 'Period Ends',
      size: 110,
      cell: ({ getValue }) => fmtDate(getValue()),
    },
    {
      id: 'actions',
      header: 'Actions',
      size: 100,
      cell: ({ row }) => (
        <button onClick={() => onReset(row.original)} style={actionBtnStyle()}>
          Reset
        </button>
      ),
    },
  ];
}

function actionBtnStyle(accent = false) {
  return {
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: 12,
    cursor: 'pointer',
    border: `1px solid ${accent ? 'var(--color-admin-accent)' : 'var(--color-admin-border)'}`,
    background: accent ? 'var(--color-admin-accent-bg)' : 'var(--color-admin-surface)',
    color: accent ? 'var(--color-admin-accent-text)' : 'var(--color-admin-mid)',
  };
}

// ── sub-components ────────────────────────────────────────────────────────────

function UsageTable({ data, onReset }) {
  const columns = useMemo(() => buildColumns(onReset), [onReset]);
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });

  return (
    <div
      style={{ overflowX: 'auto', borderRadius: 10, border: '1px solid var(--color-admin-border)' }}
    >
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} style={{ background: 'var(--color-admin-bg)' }}>
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  style={{
                    padding: '10px 14px',
                    textAlign: 'left',
                    fontWeight: 600,
                    color: 'var(--color-admin-mid)',
                    fontSize: 12,
                    whiteSpace: 'nowrap',
                    borderBottom: '1px solid var(--color-admin-border)',
                  }}
                >
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
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    style={{ padding: '11px 14px', color: 'var(--color-admin-text)' }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </motion.tr>
            ))}
          </AnimatePresence>
          {table.getRowModel().rows.length === 0 && (
            <tr>
              <td
                colSpan={columns.length}
                style={{ padding: '32px', textAlign: 'center', color: 'var(--color-admin-mid)' }}
              >
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
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginTop: 16,
        fontSize: 13,
      }}
    >
      <span style={{ color: 'var(--color-admin-mid)' }}>
        Page {page} of {totalPages} · {total} accounts
      </span>
      <div style={{ display: 'flex', gap: 8 }}>
        <PageBtn icon="mdi:chevron-left" onClick={() => onPage(page - 1)} disabled={page <= 1} />
        <PageBtn icon="mdi:chevron-right" onClick={() => onPage(page + 1)} disabled={!hasMore} />
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
        width: 32,
        height: 32,
        border: '1px solid var(--color-admin-border)',
        borderRadius: 6,
        background: disabled ? 'transparent' : 'var(--color-admin-surface)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
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
  const [data, setData] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [loading, setLoading] = useState(true);

  const [prevQuery, setPrevQuery] = useState([page, search]);
  if (page !== prevQuery[0] || search !== prevQuery[1]) {
    setPrevQuery([page, search]);
    if (token) setLoading(true);
  }

  const fetchAccounts = useCallback(
    (p, s) => {
      if (!token) return;
      adminApi
        .getBillingAccounts(token, { page: p, limit: LIMIT, search: s })
        .then((res) => {
          setData(res.data ?? []);
          setTotal(res.total ?? 0);
          setHasMore(res.has_more ?? false);
        })
        .catch((e) => showError(e, "Couldn't load usage accounts — please try again."))
        .finally(() => setLoading(false));
    },
    [token]
  );

  useEffect(() => {
    fetchAccounts(page, search);
  }, [page, search, fetchAccounts]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  };

  const handleReset = async (account) => {
    if (!window.confirm(`Reset usage for ${account.email} to their tier's default allowance?`))
      return;
    try {
      await adminApi.resetUsage(token, account.user_id);
      showSuccess('Usage reset.');
      fetchAccounts(page, search);
    } catch (e) {
      showError(e, "Couldn't reset usage — please try again.");
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
          {total} billing accounts — one shared monthly credit pool per user (token-weighted). Reset
          refills to the tier budget.
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
                position: 'absolute',
                left: 10,
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--color-admin-muted)',
                fontSize: 16,
                pointerEvents: 'none',
              }}
            />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by email…"
              style={{
                width: '100%',
                padding: '8px 10px 8px 32px',
                border: '1px solid var(--color-admin-border)',
                borderRadius: 8,
                background: 'var(--color-admin-input-bg)',
                color: 'var(--color-admin-text)',
                fontSize: 13,
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <button
            type="submit"
            style={{
              padding: '8px 14px',
              borderRadius: 8,
              border: 'none',
              background: 'var(--color-admin-accent)',
              color: '#fff',
              fontSize: 13,
              cursor: 'pointer',
              fontWeight: 500,
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
            <Icon
              icon="mdi:loading"
              style={{ fontSize: 24, animation: 'spin 1s linear infinite' }}
            />
          </div>
        ) : (
          <UsageTable data={data} onReset={handleReset} />
        )}

        <Pagination page={page} hasMore={hasMore} total={total} limit={LIMIT} onPage={setPage} />
      </motion.div>
    </div>
  );
}

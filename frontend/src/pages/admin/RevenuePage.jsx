import { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  useReactTable, getCoreRowModel, flexRender,
} from '@tanstack/react-table';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { adminApi } from '@/features/admin/adminApi';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtVnd(n) {
  return `${(n ?? 0).toLocaleString('vi-VN')}đ`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });
}

function fmtDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

const TYPE_LABELS = { subscription_upgrade: 'Subscription', topup: 'Top-up' };

// ── animation presets ─────────────────────────────────────────────────────────

const fadeUp = {
  hidden:  { opacity: 0, y: 16 },
  visible: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.07, type: 'spring', stiffness: 260, damping: 28 },
  }),
};

// ── sub-components ────────────────────────────────────────────────────────────

function StatCard({ icon, label, value, color, delay }) {
  return (
    <motion.div
      custom={delay}
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      style={{
        background: 'var(--color-admin-surface)',
        border: '1px solid var(--color-admin-border)',
        borderRadius: 12,
        padding: '20px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        flex: 1,
        minWidth: 0,
      }}
    >
      <div style={{
        width: 44, height: 44, borderRadius: 10,
        background: color + '22',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Icon icon={icon} style={{ fontSize: 22, color }} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--color-admin-text)', lineHeight: 1.2 }}>
          {value ?? '—'}
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-admin-mid)', marginTop: 2 }}>{label}</div>
      </div>
    </motion.div>
  );
}

const TRANSACTION_COLUMNS = [
  { accessorKey: 'email', header: 'Email', size: 220, cell: ({ getValue }) => getValue() ?? '—' },
  {
    accessorKey: 'type',
    header: 'Type',
    size: 110,
    cell: ({ getValue }) => {
      const v = getValue();
      const styles = {
        subscription_upgrade: { background: 'rgba(59,130,246,0.12)', color: 'var(--color-admin-accent-text)' },
        topup:                { background: 'rgba(16,185,129,0.12)', color: '#10b981' },
      };
      const s = styles[v] ?? { background: 'var(--color-admin-role-bg)', color: 'var(--color-admin-mid)' };
      return (
        <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600, ...s }}>
          {TYPE_LABELS[v] ?? v}
        </span>
      );
    },
  },
  {
    accessorKey: 'tier',
    header: 'Plan / Pack',
    size: 120,
    cell: ({ row }) => row.original.tier ?? row.original.topup_pack ?? '—',
  },
  {
    accessorKey: 'amount_vnd',
    header: 'Amount',
    size: 110,
    cell: ({ getValue }) => fmtVnd(getValue()),
  },
  {
    accessorKey: 'paid_at',
    header: 'Paid at',
    size: 140,
    cell: ({ getValue }) => fmtDateTime(getValue()),
  },
];

function TransactionsTable({ data }) {
  const table = useReactTable({ data, columns: TRANSACTION_COLUMNS, getCoreRowModel: getCoreRowModel() });

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
          {table.getRowModel().rows.map((row, i) => (
            <motion.tr
              key={row.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              style={{ borderBottom: '1px solid var(--color-admin-border)' }}
            >
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} style={{ padding: '10px 14px', color: 'var(--color-admin-text)' }}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </motion.tr>
          ))}
          {table.getRowModel().rows.length === 0 && (
            <tr>
              <td colSpan={5} style={{ padding: '24px', textAlign: 'center', color: 'var(--color-admin-mid)' }}>
                No paid transactions yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function RevenuePage() {
  const token = useAuthStore((s) => s.token);
  const [revenue, setRevenue] = useState(null);
  const [loading, setLoading] = useState(true);

  // Flip the loading flag the moment `token` changes (render-time adjustment,
  // not inside the effect) — same pattern as DashboardPage.jsx.
  const [prevToken, setPrevToken] = useState(token);
  if (token !== prevToken) {
    setPrevToken(token);
    if (token) setLoading(true);
  }

  useEffect(() => {
    if (!token) return;
    adminApi.getRevenue(token)
      .then(setRevenue)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  const chartData = useMemo(
    () => (revenue?.daily ?? []).map((d) => ({ ...d, dateLabel: fmtDate(d.date + 'T00:00:00') })),
    [revenue]
  );

  const CARDS = [
    { icon: 'mdi:cash-multiple',      label: 'Total Revenue',     value: fmtVnd(revenue?.total_revenue_vnd),       color: '#10b981', delay: 0 },
    { icon: 'mdi:calendar-month-outline', label: 'This Month',    value: fmtVnd(revenue?.revenue_this_month_vnd),  color: '#3b82f6', delay: 1 },
    { icon: 'mdi:receipt-text-outline', label: 'Paid Transactions', value: revenue?.total_paid_transactions,       color: '#f59e0b', delay: 2 },
    { icon: 'mdi:chart-line',         label: 'Avg Transaction',   value: fmtVnd(revenue?.avg_transaction_vnd),     color: '#8b5cf6', delay: 3 },
  ];

  return (
    <div>
      {/* Header */}
      <motion.div variants={fadeUp} custom={0} initial="hidden" animate="visible" style={{ marginBottom: 28 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: 'var(--color-admin-text)' }}>Revenue</h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-admin-mid)' }}>
          PayOS payments — subscriptions and top-ups
        </p>
      </motion.div>

      {/* Stat Cards */}
      {loading ? (
        <div style={{ display: 'flex', gap: 16, marginBottom: 28 }}>
          {[0, 1, 2, 3].map(i => (
            <div key={i} style={{
              flex: 1, height: 88, borderRadius: 12,
              background: 'var(--color-admin-surface)',
              border: '1px solid var(--color-admin-border)',
              animation: 'pulse 1.5s ease-in-out infinite',
            }} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
          {CARDS.map(c => <StatCard key={c.label} {...c} />)}
        </div>
      )}

      {/* Chart */}
      <motion.div
        variants={fadeUp} custom={4} initial="hidden" animate="visible"
        style={{
          background: 'var(--color-admin-surface)',
          border: '1px solid var(--color-admin-border)',
          borderRadius: 12, padding: '20px 24px', marginBottom: 28,
        }}
      >
        <h2 style={{ margin: '0 0 16px', fontSize: 15, fontWeight: 600, color: 'var(--color-admin-text)' }}>
          Revenue (last 30 days)
        </h2>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}   />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-admin-border)" />
            <XAxis dataKey="dateLabel" tick={{ fontSize: 11, fill: 'var(--color-admin-mid)' }} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--color-admin-mid)' }} axisLine={false} tickLine={false} />
            <Tooltip
              formatter={(value) => fmtVnd(value)}
              contentStyle={{
                background: 'var(--color-admin-surface)',
                border: '1px solid var(--color-admin-border)',
                borderRadius: 8, fontSize: 12, color: 'var(--color-admin-text)',
              }}
            />
            <Area type="monotone" dataKey="revenue_vnd" name="Revenue" stroke="#10b981" fill="url(#revenueGrad)" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Recent transactions */}
      <motion.div variants={fadeUp} custom={5} initial="hidden" animate="visible">
        <h2 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: 'var(--color-admin-text)' }}>
          Recent Transactions
        </h2>
        <TransactionsTable data={revenue?.recent ?? []} />
      </motion.div>
    </div>
  );
}

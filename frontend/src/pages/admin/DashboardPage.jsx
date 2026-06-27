import { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  useReactTable, getCoreRowModel, flexRender,
} from '@tanstack/react-table';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { adminApi } from '@/features/admin/adminApi';

// ── helpers ───────────────────────────────────────────────────────────────────

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

function buildChartData(activities) {
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    return d.toISOString().slice(0, 10);
  });
  const map = {};
  days.forEach(d => { map[d] = { date: fmtDate(d + 'T00:00:00'), logins: 0, registers: 0 }; });
  activities.forEach(({ event_type, logged_in_at }) => {
    const day = logged_in_at?.slice(0, 10);
    if (map[day]) {
      if (event_type === 'login' || event_type === 'google_login') map[day].logins += 1;
      if (event_type === 'register') map[day].registers += 1;
    }
  });
  return Object.values(map);
}

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

const ACTIVITY_COLUMNS = [
  { accessorKey: 'email', header: 'Email', size: 220 },
  {
    accessorKey: 'event_type',
    header: 'Event',
    size: 100,
    cell: ({ getValue }) => {
      const v = getValue();
      const styles = {
        login:    { background: 'rgba(59,130,246,0.12)',  color: 'var(--color-admin-accent-text)' },
        register: { background: 'rgba(16,185,129,0.12)', color: '#10b981' },
        logout:   { background: 'rgba(239,68,68,0.12)',  color: '#ef4444' },
      };
      const s = styles[v] ?? { background: 'var(--color-admin-role-bg)', color: 'var(--color-admin-mid)' };
      return (
        <span style={{
          display: 'inline-block', padding: '2px 10px', borderRadius: 20,
          fontSize: 11, fontWeight: 600, ...s,
        }}>
          {v}
        </span>
      );
    },
  },
  {
    accessorKey: 'logged_in_at',
    header: 'Time',
    size: 140,
    cell: ({ getValue }) => fmtDateTime(getValue()),
  },
  { accessorKey: 'ip_address', header: 'IP', size: 120, cell: ({ getValue }) => getValue() ?? '—' },
];

function ActivityTable({ data }) {
  const table = useReactTable({ data, columns: ACTIVITY_COLUMNS, getCoreRowModel: getCoreRowModel() });

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
              <td colSpan={4} style={{ padding: '24px', textAlign: 'center', color: 'var(--color-admin-mid)' }}>
                No activity yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const token = useAuthStore((s) => s.token);
  const [stats,      setStats]      = useState(null);
  const [activities, setActivities] = useState([]);
  const [loading,    setLoading]    = useState(true);

  // Flip the loading flag the moment `token` changes (render-time adjustment,
  // not inside the effect) — avoids a synchronous setState within the effect
  // body while still showing the spinner immediately on token change.
  const [prevToken, setPrevToken] = useState(token);
  if (token !== prevToken) {
    setPrevToken(token);
    if (token) setLoading(true);
  }

  useEffect(() => {
    if (!token) return;
    const since = new Date(Date.now() - 7 * 86_400_000).toISOString();
    Promise.all([
      adminApi.getStats(token),
      adminApi.getActivity(token, { page: 1, limit: 500, since }),
    ])
      .then(([s, a]) => { setStats(s); setActivities(a.data ?? []); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  const chartData = useMemo(() => buildChartData(activities), [activities]);
  const tableData = useMemo(() => activities.slice(0, 10), [activities]);

  const CARDS = [
    { icon: 'mdi:account-multiple',     label: 'Total Users',     value: stats?.total_users,         color: '#3b82f6', delay: 0 },
    { icon: 'mdi:account-plus-outline', label: 'New This Week',   value: stats?.new_users_this_week, color: '#10b981', delay: 1 },
    { icon: 'mdi:login',                label: 'Logins Today',    value: stats?.total_logins_today,  color: '#f59e0b', delay: 2 },
    { icon: 'mdi:pulse',                label: 'Active (7 days)', value: stats?.active_users_7d,     color: '#8b5cf6', delay: 3 },
  ];

  return (
    <div>
      {/* Header */}
      <motion.div variants={fadeUp} custom={0} initial="hidden" animate="visible" style={{ marginBottom: 28 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: 'var(--color-admin-text)' }}>Dashboard</h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-admin-mid)' }}>
          Overview of platform activity
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
          Activity (last 7 days)
        </h2>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={chartData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="loginGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}   />
              </linearGradient>
              <linearGradient id="regGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}   />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-admin-border)" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--color-admin-mid)' }} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--color-admin-mid)' }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{
              background: 'var(--color-admin-surface)',
              border: '1px solid var(--color-admin-border)',
              borderRadius: 8, fontSize: 12, color: 'var(--color-admin-text)',
            }} />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            <Area type="monotone" dataKey="logins"    name="Logins"    stroke="#3b82f6" fill="url(#loginGrad)" strokeWidth={2} dot={false} />
            <Area type="monotone" dataKey="registers" name="Registers" stroke="#10b981" fill="url(#regGrad)"   strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Activity Table */}
      <motion.div variants={fadeUp} custom={5} initial="hidden" animate="visible">
        <h2 style={{ margin: '0 0 12px', fontSize: 15, fontWeight: 600, color: 'var(--color-admin-text)' }}>
          Recent Activity
        </h2>
        <ActivityTable data={tableData} />
      </motion.div>
    </div>
  );
}

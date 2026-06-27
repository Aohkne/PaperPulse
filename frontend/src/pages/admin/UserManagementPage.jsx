import { useEffect, useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import {
  useReactTable, getCoreRowModel, flexRender,
} from '@tanstack/react-table';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { adminApi } from '@/features/admin/adminApi';
import { showError } from '@/shared/utils/toast';

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
}

function RoleBadge({ role }) {
  const isAdmin = role === 'admin';
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 20,
      fontSize: 11, fontWeight: 600,
      background: isAdmin ? 'var(--color-admin-accent-bg)' : 'var(--color-admin-role-bg)',
      color:      isAdmin ? 'var(--color-admin-accent-text)' : 'var(--color-admin-mid)',
      border:     `1px solid ${isAdmin ? 'var(--color-admin-role-border)' : 'var(--color-admin-border)'}`,
    }}>
      {role}
    </span>
  );
}

function StatusBadge({ isBanned }) {
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: 20,
      fontSize: 11, fontWeight: 600,
      background: isBanned ? '#fed7d7' : 'var(--color-admin-role-bg)',
      color:      isBanned ? '#c0392b' : 'var(--color-admin-mid)',
      border:     `1px solid ${isBanned ? '#e8a8a8' : 'var(--color-admin-border)'}`,
    }}>
      {isBanned ? 'Banned' : 'Active'}
    </span>
  );
}

// ── table columns ─────────────────────────────────────────────────────────────

function buildColumns(onBan, onUnban) {
  return [
    { accessorKey: 'email',        header: 'Email',      size: 220 },
    {
      accessorKey: 'full_name',
      header: 'Name',
      size: 140,
      cell: ({ getValue }) => getValue() || <span style={{ color: 'var(--color-admin-muted)' }}>—</span>,
    },
    {
      accessorKey: 'role',
      header: 'Role',
      size: 90,
      cell: ({ getValue }) => <RoleBadge role={getValue()} />,
    },
    {
      accessorKey: 'is_banned',
      header: 'Status',
      size: 90,
      cell: ({ getValue }) => <StatusBadge isBanned={getValue()} />,
    },
    {
      accessorKey: 'created_at',
      header: 'Joined',
      size: 110,
      cell: ({ getValue }) => fmtDate(getValue()),
    },
    {
      accessorKey: 'last_login',
      header: 'Last Login',
      size: 110,
      cell: ({ getValue }) => fmtDate(getValue()),
    },
    {
      accessorKey: 'total_logins',
      header: 'Logins',
      size: 70,
      cell: ({ getValue }) => <span style={{ fontVariantNumeric: 'tabular-nums' }}>{getValue()}</span>,
    },
    {
      id: 'actions',
      header: 'Actions',
      size: 90,
      cell: ({ row }) => {
        const u = row.original;
        return u.is_banned ? (
          <button onClick={() => onUnban(u.id)} style={actionBtnStyle()}>Unban</button>
        ) : (
          <button onClick={() => onBan(u.id)} style={actionBtnStyle(true)}>Ban</button>
        );
      },
    },
  ];
}

function actionBtnStyle(danger = false) {
  return {
    padding: '4px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer',
    border: `1px solid ${danger ? '#e8a8a8' : 'var(--color-admin-border)'}`,
    background: danger ? '#fff5f5' : 'var(--color-admin-surface)',
    color: danger ? '#c0392b' : 'var(--color-admin-mid)',
  };
}

// ── sub-components ────────────────────────────────────────────────────────────

function UserTable({ data, onBan, onUnban }) {
  const columns = useMemo(() => buildColumns(onBan, onUnban), [onBan, onUnban]);
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
                No users found
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
        Page {page} of {totalPages} · {total} users
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

export default function UserManagementPage() {
  const token = useAuthStore((s) => s.token);
  const [data,        setData]        = useState([]);
  const [total,       setTotal]       = useState(0);
  const [page,        setPage]        = useState(1);
  const [hasMore,     setHasMore]     = useState(false);
  const [search,      setSearch]      = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [roleFilter,  setRoleFilter]  = useState('');
  const [loading,     setLoading]     = useState(true);

  // Flip the loading flag the moment the query params change (render-time
  // adjustment, not inside the effect) — avoids a synchronous setState
  // within the effect body while still showing the spinner immediately.
  const [prevQuery, setPrevQuery] = useState([page, search, roleFilter]);
  if (page !== prevQuery[0] || search !== prevQuery[1] || roleFilter !== prevQuery[2]) {
    setPrevQuery([page, search, roleFilter]);
    if (token) setLoading(true);
  }

  const fetchUsers = useCallback((p, s, r) => {
    if (!token) return;
    adminApi
      .getUsers(token, { page: p, limit: LIMIT, search: s, role: r })
      .then(res => {
        setData(res.data ?? []);
        setTotal(res.total ?? 0);
        setHasMore(res.has_more ?? false);
      })
      .catch((e) => showError(e, "Couldn't load users — please try again."))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { fetchUsers(page, search, roleFilter); }, [page, search, roleFilter, fetchUsers]);

  const handleSearch = (e) => { e.preventDefault(); setPage(1); setSearch(searchInput); };
  const handleRole   = (r)  => { setRoleFilter(r); setPage(1); };

  const handleBan = async (id) => {
    const reason = window.prompt('Reason for banning this user:');
    if (reason === null) return;
    await adminApi.banUser(token, id, reason || 'No reason provided');
    fetchUsers(page, search, roleFilter);
  };

  const handleUnban = async (id) => {
    if (!window.confirm('Unban this user?')) return;
    await adminApi.unbanUser(token, id);
    fetchUsers(page, search, roleFilter);
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
          User Management
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-admin-mid)' }}>
          {total} registered accounts
        </p>
      </motion.div>

      {/* Toolbar */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
        style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}
      >
        {/* Search */}
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 6, flex: 1, minWidth: 200 }}>
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

        {/* Role filter */}
        <div style={{ display: 'flex', gap: 4 }}>
          {['', 'admin', 'user'].map(r => (
            <button
              key={r || 'all'}
              onClick={() => handleRole(r)}
              style={{
                padding: '6px 12px', borderRadius: 8, border: '1px solid',
                borderColor:  roleFilter === r ? 'var(--color-admin-accent)' : 'var(--color-admin-border)',
                background:   roleFilter === r ? 'var(--color-admin-accent-bg)' : 'transparent',
                color:        roleFilter === r ? 'var(--color-admin-accent-text)' : 'var(--color-admin-mid)',
                fontSize: 12, fontWeight: roleFilter === r ? 600 : 400,
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              {r === '' ? 'All' : r}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Table */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.12 }}>
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-admin-mid)' }}>
            <Icon icon="mdi:loading" style={{ fontSize: 24, animation: 'spin 1s linear infinite' }} />
          </div>
        ) : (
          <UserTable data={data} onBan={handleBan} onUnban={handleUnban} />
        )}

        <Pagination page={page} hasMore={hasMore} total={total} limit={LIMIT} onPage={setPage} />
      </motion.div>
    </div>
  );
}

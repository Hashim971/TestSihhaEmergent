import React, { useEffect, useState } from "react";
import { Filter, ChevronRight, ChevronLeft, Search } from "lucide-react";
import { api } from "../../lib/api";
import { StatusBadge, inputCls, labelCls } from "../../components/admin/ui";
import { UserDetailModal, ago } from "../../components/admin/UserDetailModal";

const LIMIT = 25;
const ROLE_STYLES = { patient: "bg-sky-50 text-sky-700 border-sky-200", doctor: "bg-violet-50 text-violet-700 border-violet-200", pharmacist: "bg-amber-50 text-amber-700 border-amber-200" };

export default function Users() {
  const [filters, setFilters] = useState({ q: "", role: "", status: "", include_demo: false });
  const [showFilters, setShowFilters] = useState(true);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ total: 0, items: [], demo_hidden: 0 });
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setLoading(true);
    let live = true;
    const t = setTimeout(() => api.get("/admin/users", { params: { ...filters, page, limit: LIMIT } })
      .then(({ data }) => live && setData(data)).catch(() => {}).finally(() => live && setLoading(false)), 250);
    return () => { live = false; clearTimeout(t); };
  }, [filters, page, tick]);

  const setFilter = (k, v) => { setPage(1); setFilters((f) => ({ ...f, [k]: v })); };
  const pages = Math.max(1, Math.ceil(data.total / LIMIT));

  return (
    <div className="fade-up" data-testid="users-page">
      <div className="flex flex-wrap items-center gap-3 mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight mr-auto">Users</h1>
        <button onClick={() => setShowFilters(!showFilters)} data-testid="users-filter-toggle"
          className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium ${showFilters ? "bg-ink text-white" : "border border-line bg-white"}`}>
          <Filter className="h-4 w-4" /> Filter
        </button>
      </div>

      {showFilters && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4" data-testid="users-filters">
          <div>
            <label className={labelCls}>Name, email or ID</label>
            <div className="relative">
              <Search className="h-4 w-4 text-ink-soft absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={filters.q} onChange={(e) => setFilter("q", e.target.value)} placeholder="e.g. sara@ or user_12"
                data-testid="users-search-input" className={`${inputCls} pl-9`} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Role</label>
            <select value={filters.role} onChange={(e) => setFilter("role", e.target.value)} data-testid="users-role-filter" className={inputCls}>
              <option value="">All roles</option><option value="patient">Patients</option><option value="doctor">Doctors</option><option value="pharmacist">Pharmacists</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>Status</label>
            <select value={filters.status} onChange={(e) => setFilter("status", e.target.value)} data-testid="users-status-filter" className={inputCls}>
              <option value="">All statuses</option><option value="active">Active</option><option value="suspended">Suspended</option>
            </select>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <p className="text-sm text-ink-soft" data-testid="users-count">
          Showing <span className="text-forest font-semibold">{data.items.length}</span> of <span className="text-forest font-semibold">{data.total}</span> {filters.include_demo ? "users" : "real users"}
          {!filters.include_demo && data.demo_hidden > 0 && <span> · {data.demo_hidden} demo/test accounts hidden</span>}
        </p>
        <label className="inline-flex items-center gap-2 text-sm text-ink-soft cursor-pointer">
          <input type="checkbox" checked={filters.include_demo} onChange={(e) => setFilter("include_demo", e.target.checked)}
            className="accent-[#1E3F2A]" data-testid="users-include-demo-toggle" /> Show demo accounts
        </label>
      </div>

      <div className="space-y-2" data-testid="users-list">
        {!loading && data.items.length === 0 && (
          <div className="card p-10 text-center text-sm text-ink-soft" data-testid="users-empty">No users match these filters.</div>
        )}
        {data.items.map((u) => <UserRow key={u.user_id} u={u} onOpen={() => setOpenId(u.user_id)} />)}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-6" data-testid="users-pagination">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="btn-outline disabled:opacity-40" data-testid="users-prev-page"><ChevronLeft className="h-4 w-4" /></button>
          <span className="text-sm text-ink-soft">Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)} className="btn-outline disabled:opacity-40" data-testid="users-next-page"><ChevronRight className="h-4 w-4" /></button>
        </div>
      )}

      {openId && <UserDetailModal userId={openId} onClose={() => setOpenId(null)} onChanged={() => setTick((t) => t + 1)} />}
    </div>
  );
}

function UserRow({ u, onOpen }) {
  return (
    <div data-testid={`user-row-${u.user_id}`}
      className="card px-5 py-4 flex flex-col lg:flex-row lg:items-center gap-3 hover:border-forest/30" style={{ transition: "border-color 0.2s ease" }}>
      <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
        <button onClick={onOpen} className="font-semibold text-ink hover:text-forest truncate text-left max-w-full" data-testid={`user-name-${u.user_id}`}>
          {u.name || u.email}
        </button>
        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-md border capitalize ${ROLE_STYLES[u.role] || "bg-sand border-line"}`}>{u.role}</span>
        <StatusBadge status={u.suspended ? "suspended" : "active"} testid={`user-status-${u.user_id}`} />
        {u.is_demo && <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md border bg-sand border-line text-ink-soft">Demo</span>}
        <span className="text-xs text-ink-soft truncate max-w-full">{u.email}{u.account_name ? ` · ${u.account_name}` : " · Independent"}</span>
      </div>
      <div className="flex flex-wrap items-center gap-4 shrink-0 text-xs text-ink-soft [&>*]:whitespace-nowrap">
        <span data-testid={`user-last-login-${u.user_id}`}>Signed in {ago(u.last_login_at)}</span>
        <span>Active {ago(u.last_seen_at)}</span>
        <button onClick={onOpen} data-testid={`user-open-${u.user_id}`} className="inline-flex items-center gap-1 text-sm font-medium text-ink hover:text-forest">
          Details <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

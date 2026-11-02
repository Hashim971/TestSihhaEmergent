import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Filter, Download, Plus, Pencil, ChevronRight, ChevronLeft, Search } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { rememberAccount } from "../../lib/recentAccounts";
import { StatusBadge, TypeBadge, IdChip, Modal, inputCls, labelCls, errorText } from "../../components/admin/ui";

const LIMIT = 25;

export default function Accounts() {
  const [filters, setFilters] = useState({ q: "", type: "", status: "" });
  const [showFilters, setShowFilters] = useState(true);
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ total: 0, items: [] });
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => api.get("/admin/accounts", { params: { ...filters, page, limit: LIMIT } })
      .then(({ data }) => setData(data)).catch(() => {}).finally(() => setLoading(false)), 250);
    return () => clearTimeout(t);
  }, [filters, page]);

  const setFilter = (k, v) => { setPage(1); setFilters((f) => ({ ...f, [k]: v })); };

  const open = (a, tab) => {
    rememberAccount(a);
    navigate(`/admin/accounts/${a.account_id}${tab ? `?tab=${tab}` : ""}`);
  };

  const exportCsv = async () => {
    const res = await api.get("/admin/accounts/export", { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    Object.assign(document.createElement("a"), { href: url, download: "sihha-accounts.csv" }).click();
    URL.revokeObjectURL(url);
  };

  const pages = Math.max(1, Math.ceil(data.total / LIMIT));

  return (
    <div className="fade-up" data-testid="accounts-page">
      <div className="flex flex-wrap items-center gap-3 mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight mr-auto">Accounts</h1>
        <button onClick={() => setShowFilters(!showFilters)} data-testid="accounts-filter-toggle"
          className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium ${showFilters ? "bg-ink text-white" : "border border-line bg-white"}`}>
          <Filter className="h-4 w-4" /> Filter
        </button>
        <button onClick={exportCsv} data-testid="accounts-export-btn" className="inline-flex items-center gap-2 border border-line bg-white rounded-md px-4 py-2 text-sm font-medium hover:bg-sand">
          <Download className="h-4 w-4" /> Export accounts
        </button>
        <button onClick={() => setAdding(true)} data-testid="accounts-add-btn" className="inline-flex items-center gap-2 bg-forest text-white rounded-md px-4 py-2 text-sm font-medium hover:opacity-90">
          <Plus className="h-4 w-4" /> Add account
        </button>
      </div>

      {showFilters && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6" data-testid="accounts-filters">
          <div>
            <label className={labelCls}>Name or ID</label>
            <div className="relative">
              <Search className="h-4 w-4 text-ink-soft absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={filters.q} onChange={(e) => setFilter("q", e.target.value)} placeholder="e.g. Al Noor or ACC-12AF"
                data-testid="accounts-search-input" className={`${inputCls} pl-9`} />
            </div>
          </div>
          <div>
            <label className={labelCls}>Account type</label>
            <select value={filters.type} onChange={(e) => setFilter("type", e.target.value)} data-testid="accounts-type-filter" className={inputCls}>
              <option value="">All types</option><option value="hospital">Hospital</option><option value="clinic">Clinic</option><option value="pharmacy_group">Pharmacy group</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>Status</label>
            <select value={filters.status} onChange={(e) => setFilter("status", e.target.value)} data-testid="accounts-status-filter" className={inputCls}>
              <option value="">All statuses</option><option value="subscribed">Subscribed</option><option value="trial">Trial</option><option value="suspended">Suspended</option>
            </select>
          </div>
        </div>
      )}

      <p className="text-sm text-ink-soft mb-3" data-testid="accounts-count">
        Showing <span className="text-forest font-semibold">{data.items.length}</span> of <span className="text-forest font-semibold">{data.total}</span> accounts
      </p>

      <div className="space-y-2" data-testid="accounts-list">
        {!loading && data.items.length === 0 && (
          <div className="card p-10 text-center text-sm text-ink-soft" data-testid="accounts-empty">No accounts match these filters.</div>
        )}
        {data.items.map((a) => (
          <div key={a.account_id} data-testid={`account-row-${a.account_id}`}
            className="card px-5 py-4 flex flex-col lg:flex-row lg:items-center gap-3 hover:border-forest/30" style={{ transition: "border-color 0.2s ease" }}>
            <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
              <button onClick={() => open(a)} className="font-semibold text-ink hover:text-forest truncate text-left" data-testid={`account-name-${a.account_id}`}>{a.name}</button>
              <StatusBadge status={a.status} testid={`account-status-${a.account_id}`} />
              <TypeBadge type={a.type} />
              <span className="text-xs text-ink-soft">{a.staff_count} Staff · {a.customer_count} Customers{a.city ? ` · ${a.city}` : ""}</span>
            </div>
            <div className="flex flex-wrap items-center gap-3 shrink-0 [&>*]:whitespace-nowrap">
              <button onClick={() => open(a, "branding")} data-testid={`account-edit-${a.account_id}`} className="p-2 border border-line rounded-md hover:bg-sand" title="Edit"><Pencil className="h-4 w-4" /></button>
              <IdChip id={a.account_id} testid={`account-id-${a.account_id}`} large />
              <button onClick={() => open(a)} data-testid={`account-switch-${a.account_id}`} className="inline-flex items-center gap-1 text-sm font-medium text-ink hover:text-forest">
                Switch to account <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-6" data-testid="accounts-pagination">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="btn-outline disabled:opacity-40" data-testid="accounts-prev-page"><ChevronLeft className="h-4 w-4" /></button>
          <span className="text-sm text-ink-soft">Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)} className="btn-outline disabled:opacity-40" data-testid="accounts-next-page"><ChevronRight className="h-4 w-4" /></button>
        </div>
      )}

      {adding && <AddAccountModal onClose={() => setAdding(false)} onCreated={(a) => { setAdding(false); toast.success(`Created ${a.name} · ${a.account_id}`); open(a, "onboarding"); }} />}
    </div>
  );
}

function AddAccountModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ name: "", type: "hospital", status: "trial", city: "", contact_email: "" });
  const [saving, setSaving] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.post("/admin/accounts", { ...form, city: form.city || null, contact_email: form.contact_email || null });
      onCreated(data);
    } catch (err) {
      toast.error(errorText(err, "Could not create the account"));
    } finally {
      setSaving(false);
    }
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <Modal title="Add account" onClose={onClose} testid="add-account-modal">
      <form onSubmit={submit} className="space-y-4">
        <div><label className={labelCls}>Hospital or clinic name</label><input required minLength={2} value={form.name} onChange={set("name")} data-testid="add-account-name" className={inputCls} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className={labelCls}>Type</label>
            <select value={form.type} onChange={set("type")} data-testid="add-account-type" className={inputCls}>
              <option value="hospital">Hospital</option><option value="clinic">Clinic</option><option value="pharmacy_group">Pharmacy group</option>
            </select></div>
          <div><label className={labelCls}>Status</label>
            <select value={form.status} onChange={set("status")} data-testid="add-account-status" className={inputCls}>
              <option value="trial">Trial</option><option value="subscribed">Subscribed</option>
            </select></div>
        </div>
        <div><label className={labelCls}>City</label><input value={form.city} onChange={set("city")} data-testid="add-account-city" className={inputCls} /></div>
        <div><label className={labelCls}>Contact email</label><input type="email" value={form.contact_email} onChange={set("contact_email")} data-testid="add-account-email" className={inputCls} /></div>
        <p className="text-xs text-ink-soft">A unique account ID (ACC-XXXXXX) is created automatically.</p>
        <button disabled={saving} data-testid="add-account-submit" className="btn-primary w-full justify-center">{saving ? "Creating…" : "Create account"}</button>
      </form>
    </Modal>
  );
}

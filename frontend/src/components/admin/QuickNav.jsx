import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Building2, User, CornerDownLeft } from "lucide-react";
import { api } from "../../lib/api";
import { rememberAccount } from "../../lib/recentAccounts";

export function QuickNav({ open, onClose }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState({ accounts: [], users: [] });
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) setQ("");
  }, [open]);

  useEffect(() => {
    if (!q.trim()) return setRes({ accounts: [], users: [] });
    const t = setTimeout(() => api.get("/admin/search", { params: { q } }).then(({ data }) => setRes(data)).catch(() => {}), 200);
    return () => clearTimeout(t);
  }, [q]);

  if (!open) return null;

  const goAccount = (a) => {
    rememberAccount(a);
    onClose();
    navigate(`/admin/accounts/${a.account_id}`);
  };
  const goUser = (u) => {
    onClose();
    if (u.account_id) navigate(`/admin/accounts/${u.account_id}?tab=${u.role === "patient" ? "customers" : "staff"}&q=${encodeURIComponent(u.email)}`);
    else navigate(`/admin/assignments`);
  };

  return (
    <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4" onClick={onClose}>
      <div className="w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-line overflow-hidden fade-up" onClick={(e) => e.stopPropagation()} data-testid="quick-nav-modal">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-line">
          <Search className="h-5 w-5 text-ink-soft" />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Escape" && onClose()}
            placeholder="Search accounts by name or ID, people by name or email…" data-testid="quick-nav-input"
            className="flex-1 text-base focus:outline-none" />
          <kbd className="text-[10px] font-mono border border-line rounded px-1.5 py-0.5 text-ink-soft">ESC</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto p-2">
          {!q.trim() && <p className="px-3 py-6 text-sm text-ink-soft text-center">Type to jump to any hospital account or person.</p>}
          {q.trim() && res.accounts.length + res.users.length === 0 && (
            <p className="px-3 py-6 text-sm text-ink-soft text-center" data-testid="quick-nav-empty">No matches for “{q}”.</p>
          )}
          {res.accounts.length > 0 && <p className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-[0.15em] text-ink-soft font-semibold">Accounts</p>}
          {res.accounts.map((a) => (
            <button key={a.account_id} onClick={() => goAccount(a)} data-testid={`quick-nav-account-${a.account_id}`}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-sand text-left group">
              <Building2 className="h-4 w-4 text-forest" />
              <span className="flex-1 truncate text-sm font-medium">{a.name}</span>
              <span className="font-mono text-xs text-ink-soft">{a.account_id}</span>
              <CornerDownLeft className="h-3.5 w-3.5 text-ink-soft opacity-0 group-hover:opacity-100" />
            </button>
          ))}
          {res.users.length > 0 && <p className="px-3 pt-3 pb-1 text-[10px] uppercase tracking-[0.15em] text-ink-soft font-semibold">People</p>}
          {res.users.map((u) => (
            <button key={u.user_id} onClick={() => goUser(u)} data-testid={`quick-nav-user-${u.user_id}`}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-sand text-left">
              <User className="h-4 w-4 text-ink-soft" />
              <span className="flex-1 min-w-0">
                <span className="block truncate text-sm font-medium">{u.name}</span>
                <span className="block truncate text-xs text-ink-soft">{u.email}</span>
              </span>
              <span className="text-[11px] capitalize text-ink-soft">{u.role === "doctor" ? "Staff" : "Customer"}</span>
              <span className="font-mono text-[10px] text-ink-soft">{u.account_id || "no account"}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

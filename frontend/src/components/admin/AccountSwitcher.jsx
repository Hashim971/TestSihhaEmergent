import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, ChevronDown, Search } from "lucide-react";
import { api } from "../../lib/api";
import { getCurrentAccount, getRecentAccounts, rememberAccount } from "../../lib/recentAccounts";

export function AccountSwitcher() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [current, setCurrent] = useState(getCurrentAccount());
  const navigate = useNavigate();
  const box = useRef(null);

  useEffect(() => {
    const sync = () => setCurrent(getCurrentAccount());
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    window.addEventListener("sihha:account-switched", sync);
    document.addEventListener("mousedown", close);
    return () => {
      window.removeEventListener("sihha:account-switched", sync);
      document.removeEventListener("mousedown", close);
    };
  }, []);

  useEffect(() => {
    if (!q.trim()) return setResults([]);
    const t = setTimeout(() => api.get("/admin/accounts", { params: { q, limit: 8 } })
      .then(({ data }) => setResults(data.items)).catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [q]);

  const pick = (a) => {
    rememberAccount(a);
    setOpen(false);
    setQ("");
    navigate(`/admin/accounts/${a.account_id}`);
  };

  const list = q.trim() ? results : getRecentAccounts();

  return (
    <div className="relative" ref={box}>
      <button onClick={() => setOpen(!open)} data-testid="account-switcher-btn"
        className={`w-full flex items-center gap-2 border rounded-lg px-3 py-2 bg-white text-sm ${open ? "border-forest ring-2 ring-sage" : "border-line hover:border-forest/40"}`}
        style={{ transition: "border-color 0.2s ease" }}>
        <Building2 className="h-4 w-4 text-ink-soft shrink-0" />
        <span className="truncate flex-1 text-left font-medium" data-testid="account-switcher-current">
          {current?.name || "Choose an account"}
        </span>
        {current ? (
          <span className="font-mono text-[10px] border border-line rounded px-1.5 py-0.5 text-ink-soft" title={current.account_id}>ID</span>
        ) : <ChevronDown className="h-3.5 w-3.5 text-ink-soft" />}
      </button>
      {open && (
        <div className="absolute left-0 right-0 mt-2 bg-white border border-line rounded-xl shadow-lg z-40 overflow-hidden fade-up" data-testid="account-switcher-menu">
          <div className="p-2 border-b border-line flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-ink-soft ml-1" />
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or ID"
              data-testid="account-switcher-search" className="w-full text-sm py-1 focus:outline-none" />
          </div>
          <p className="px-3 pt-3 pb-1 text-[10px] uppercase tracking-[0.15em] text-ink-soft font-semibold">
            {q.trim() ? "Results" : "Recent accounts"}
          </p>
          <div className="max-h-72 overflow-y-auto pb-1">
            {list.length === 0 && <p className="px-3 py-3 text-xs text-ink-soft">{q.trim() ? "No accounts match." : "Accounts you open appear here."}</p>}
            {list.map((a) => (
              <button key={a.account_id} onClick={() => pick(a)} data-testid={`account-switcher-option-${a.account_id}`}
                className={`w-full text-left px-3 py-2.5 text-sm hover:bg-sand flex items-center justify-between gap-2 ${current?.account_id === a.account_id ? "bg-sand" : ""}`}>
                <span className="truncate">{a.name}</span>
                <span className="font-mono text-[10px] text-ink-soft shrink-0">{a.account_id}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

import React, { useCallback, useEffect, useState } from "react";
import { Search, UserPlus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { StatusBadge, Modal, inputCls, labelCls, errorText } from "./ui";

export function PeopleTab({ accountId, kind, initialQuery = "", readOnly = false, base }) {
  const [q, setQ] = useState(initialQuery);
  const [data, setData] = useState({ total: null, items: [] });
  const [inviting, setInviting] = useState(false);
  const endpoint = base || `/admin/accounts/${accountId}/users`;

  const load = useCallback(() => api.get(endpoint, { params: { kind, q } }).then(({ data }) => setData(data)).catch(() => {}), [endpoint, kind, q]);

  useEffect(() => {
    const t = setTimeout(load, 200);
    return () => clearTimeout(t);
  }, [load]);

  const update = async (userId, patch) => {
    try {
      await api.patch(`/admin/accounts/${accountId}/users/${userId}`, patch);
      toast.success("Updated");
      load();
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  const remove = async (u) => {
    if (!window.confirm(`Remove ${u.name} from this account? Their own records are kept.`)) return;
    await api.delete(`/admin/accounts/${accountId}/users/${u.user_id}`);
    toast.success("Removed from account");
    load();
  };

  const isCustomers = kind === "customers";

  return (
    <div data-testid={`account-${kind}-tab`}>
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="h-4 w-4 text-ink-soft absolute left-3 top-1/2 -translate-y-1/2" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name or email" data-testid={`${kind}-search-input`} className={`${inputCls} pl-9`} />
        </div>
        <span className="text-sm text-ink-soft mr-auto" data-testid={`${kind}-count`}>{data.total === null ? "Loading…" : `${data.total} ${isCustomers ? (data.total === 1 ? "customer" : "customers") : "staff"}`}</span>
        {!readOnly && (
          <button onClick={() => setInviting(true)} data-testid={`${kind}-invite-btn`} className="inline-flex items-center gap-2 bg-ink text-white rounded-md px-4 py-2 text-sm font-medium hover:opacity-90">
            <UserPlus className="h-4 w-4" /> {isCustomers ? "Add customer" : "Invite user"}
          </button>
        )}
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="bg-sand text-left text-xs uppercase tracking-wider text-ink-soft">
            <tr>
              <th className="px-4 py-3 font-semibold">Name</th>
              <th className="px-4 py-3 font-semibold">Email</th>
              <th className="px-4 py-3 font-semibold">{isCustomers ? "History" : "Status"}</th>
              <th className="px-4 py-3 font-semibold">{isCustomers ? "Status" : "Role"}</th>
              {!readOnly && <th className="px-4 py-3" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.total !== null && data.items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-10 text-center text-ink-soft" data-testid={`${kind}-empty`}>No one matches yet.</td></tr>
            )}
            {data.items.map((u) => (
              <tr key={u.user_id} data-testid={`${kind}-row-${u.user_id}`} className="hover:bg-sand/50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="h-8 w-8 rounded-full bg-sage/40 text-forest flex items-center justify-center text-xs font-bold shrink-0">{(u.name || "?").charAt(0).toUpperCase()}</span>
                    <span className="font-medium">{u.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-ink-soft">{u.email}</td>
                <td className="px-4 py-3">
                  {isCustomers ? (
                    u.history ? (
                      <span className="text-xs text-ink-soft" data-testid={`customer-history-${u.user_id}`}>
                        {[...(u.history.conditions || []), ...(u.history.medications || [])].slice(0, 3).join(", ") || "Imported"}
                        {u.history.last_visit ? ` · last visit ${u.history.last_visit}` : ""}
                      </span>
                    ) : <span className="text-xs text-ink-soft">—</span>
                  ) : <StatusBadge status={u.status} />}
                </td>
                <td className="px-4 py-3">
                  {isCustomers ? <StatusBadge status={u.status} /> : readOnly ? (
                    <span className="text-xs">{u.account_role === "account_admin" ? "Hospital admin" : "Doctor"}</span>
                  ) : (
                    <select value={u.account_role} onChange={(e) => update(u.user_id, { account_role: e.target.value })} data-testid={`staff-role-select-${u.user_id}`}
                      className="border border-line rounded-md px-2 py-1.5 text-sm bg-white">
                      <option value="member">Doctor</option>
                      <option value="account_admin">Hospital admin</option>
                    </select>
                  )}
                </td>
                {!readOnly && (
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => remove(u)} data-testid={`remove-user-${u.user_id}`} className="p-1.5 rounded hover:bg-red-50 text-ink-soft hover:text-red-600" title="Remove from account">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {inviting && <InviteModal accountId={accountId} kind={kind} onClose={() => setInviting(false)} onDone={() => { setInviting(false); load(); }} />}
    </div>
  );
}

function InviteModal({ accountId, kind, onClose, onDone }) {
  const staff = kind === "staff";
  const [form, setForm] = useState({ name: "", email: "", role: staff ? "doctor" : "patient", account_role: "member" });
  const [saving, setSaving] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.post(`/admin/accounts/${accountId}/users`, form);
      toast.success(data.invited ? `Invite email sent to ${form.email}` : `${form.email} added to this account`);
      onDone();
    } catch (err) {
      toast.error(errorText(err, "Could not invite"));
    } finally {
      setSaving(false);
    }
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <Modal title={staff ? "Invite staff member" : "Add customer"} onClose={onClose} testid="invite-user-modal">
      <form onSubmit={submit} className="space-y-4">
        <div><label className={labelCls}>Full name</label><input required value={form.name} onChange={set("name")} data-testid="invite-name-input" className={inputCls} /></div>
        <div><label className={labelCls}>Email</label><input required type="email" value={form.email} onChange={set("email")} data-testid="invite-email-input" className={inputCls} /></div>
        {staff && (
          <div><label className={labelCls}>Role</label>
            <select value={form.account_role} onChange={set("account_role")} data-testid="invite-role-select" className={inputCls}>
              <option value="member">Doctor</option>
              <option value="account_admin">Hospital admin (doctor + sees the hospital overview)</option>
            </select></div>
        )}
        <p className="text-xs text-ink-soft">New people get an email with a link to set their password (valid 7 days). Existing Sihha users are simply added.</p>
        <button disabled={saving} data-testid="invite-submit-btn" className="btn-primary w-full justify-center">{saving ? "Sending…" : staff ? "Send invite" : "Add customer"}</button>
      </form>
    </Modal>
  );
}

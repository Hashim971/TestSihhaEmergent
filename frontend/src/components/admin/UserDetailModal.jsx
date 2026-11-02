import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, Ban, RotateCcw, FlaskConical } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { StatusBadge, IdChip, inputCls, labelCls, errorText } from "./ui";

export const ago = (ts) => {
  if (!ts) return "never";
  const mins = Math.round((Date.now() - new Date(ts).getTime()) / 60000);
  if (mins < 60) return mins <= 1 ? "just now" : `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} d ago`;
};

const STATS = [["active_days_30", "Active days (30d)"], ["screenings", "Screenings"], ["reports", "Reports"], ["medications", "Medications"],
  ["vitals", "Vitals logged"], ["encounters", "Visits"], ["dependents", "Family members"]];

export function UserDetailModal({ userId, onClose, onChanged }) {
  const [u, setU] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get(`/admin/users/${userId}`).then(({ data }) => setU(data)).catch(() => toast.error("Could not load user")); }, [userId]);

  const act = async (path, body, msg) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/admin/users/${userId}/${path}`, body);
      setU(data);
      toast.success(msg);
      onChanged();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-lg p-5 sm:p-6 fade-up max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="user-detail-modal">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold truncate">{u?.name || u?.email || "Loading…"}</h2>
            {u && <p className="text-sm text-ink-soft truncate">{u.email}</p>}
          </div>
          <button onClick={onClose} data-testid="user-detail-modal-close" className="p-1.5 rounded-full hover:bg-sand shrink-0"><X className="h-4 w-4" /></button>
        </div>
        {u && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={u.suspended ? "suspended" : "active"} testid="user-detail-status" />
              <span className="text-xs capitalize text-ink-soft">{u.role}{u.account_role ? ` · ${u.account_role.replace("_", " ")}` : ""}</span>
              <span className="text-xs text-ink-soft">· {u.account_name || "Independent (no hospital)"}</span>
              <IdChip id={u.user_id} testid="user-detail-id" />
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <Info label="Joined" value={u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"} />
              <Info label="Last sign-in" value={ago(u.last_login_at)} testid="user-detail-last-login" />
              <Info label="Last active" value={ago(u.last_seen_at)} />
              <Info label="Sign-in method" value={u.sign_in_method} testid="user-detail-sign-in-method" />
            </dl>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="user-detail-activity">
              {STATS.map(([k, label]) => (
                <div key={k} className="rounded-lg bg-sand px-3 py-2">
                  <p className="text-lg font-semibold" data-testid={`user-activity-${k}`}>{u.activity[k]}</p>
                  <p className="text-[11px] text-ink-soft">{label}</p>
                </div>
              ))}
            </div>
            {u.suspended && u.suspended_reason && <p className="text-sm text-red-700" data-testid="user-detail-suspend-reason">Reason: {u.suspended_reason}</p>}
            {!u.is_super_admin && (
              <div className="border-t border-line pt-4 space-y-3">
                {u.suspended ? (
                  <button disabled={busy} onClick={() => act("suspend", { suspended: false }, "User re-enabled")} className="btn-primary" data-testid="user-reenable-btn">
                    <RotateCcw className="h-4 w-4" /> Re-enable user
                  </button>
                ) : (
                  <>
                    <div>
                      <label className={labelCls}>Reason (optional)</label>
                      <input value={reason} onChange={(e) => setReason(e.target.value)} className={inputCls} data-testid="user-suspend-reason-input" />
                    </div>
                    <button disabled={busy} onClick={() => window.confirm("Suspend this user? They will be signed out and can't sign in.") && act("suspend", { suspended: true, reason }, "User suspended")}
                      className="inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium bg-red-600 text-white hover:bg-red-700 disabled:opacity-50" data-testid="user-suspend-btn">
                      <Ban className="h-4 w-4" /> Suspend user
                    </button>
                  </>
                )}
                <button disabled={busy} onClick={() => act("demo", { is_demo: !u.is_demo }, u.is_demo ? "Counted as a real user" : "Marked as demo")}
                  className="flex items-center gap-1.5 text-xs text-ink-soft underline" data-testid="user-toggle-demo-btn">
                  <FlaskConical className="h-3.5 w-3.5" /> {u.is_demo ? "This is a real user — count it" : "This is a test account — hide it from counts"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

const Info = ({ label, value, testid }) => (
  <div><dt className="text-[11px] uppercase tracking-wider text-ink-soft">{label}</dt><dd className="font-medium" data-testid={testid}>{value}</dd></div>
);

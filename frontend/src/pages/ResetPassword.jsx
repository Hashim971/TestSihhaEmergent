import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Lock, KeyRound, CheckCircle2 } from "lucide-react";
import { AuthShell, ErrorBox } from "./ForgotPassword";

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState(token ? null : "This reset link is incomplete. Request a new one.");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (password !== confirm) return setError("The two passwords don't match.");
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      window.history.replaceState(null, "", params.get("next") === "pharmacy" ? "/auth/reset?next=pharmacy" : "/auth/reset");
      setDone(true);
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <AuthShell>
        <div className="text-center" data-testid="reset-done">
          <CheckCircle2 className="h-10 w-10 text-forest mx-auto mb-3" />
          <h1 className="text-2xl font-bold tracking-tight mb-2">Password updated</h1>
          <p className="text-sm text-ink-soft mb-6">You can now sign in with your new password.</p>
          <Link to={params.get("next") === "pharmacy" ? "/auth/pharmacy" : "/auth"} data-testid="reset-signin-link" className="btn-primary mx-auto">Sign in</Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <h1 className="text-2xl font-bold tracking-tight mb-1">Choose a new password</h1>
      <p className="text-sm text-ink-soft mb-6">At least 6 characters.</p>
      {error && <ErrorBox>{error}</ErrorBox>}
      <form onSubmit={submit} className="space-y-4">
        <PasswordField value={password} onChange={setPassword} label="New password" testid="reset-password-input" />
        <PasswordField value={confirm} onChange={setConfirm} label="Confirm password" testid="reset-confirm-input" />
        <button type="submit" disabled={submitting || !token} data-testid="reset-submit-btn" className="btn-primary w-full justify-center py-3">
          <KeyRound className="h-4 w-4" /> {submitting ? "Saving…" : "Update password"}
        </button>
      </form>
      <Link to="/auth/forgot" data-testid="reset-request-new-link" className="mt-5 inline-block text-xs text-ink-soft underline">
        Request a new link
      </Link>
    </AuthShell>
  );
}

const PasswordField = ({ value, onChange, label, testid }) => (
  <div>
    <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</label>
    <div className="mt-1 flex items-center gap-2 border border-line rounded-lg px-3 py-2.5 focus-within:ring-2 focus-within:ring-forest bg-white">
      <Lock className="h-4 w-4 text-ink-soft shrink-0" />
      <input type="password" required minLength={6} value={value} onChange={(e) => onChange(e.target.value)}
        data-testid={testid} className="w-full bg-transparent text-sm focus:outline-none" />
    </div>
  </div>
);

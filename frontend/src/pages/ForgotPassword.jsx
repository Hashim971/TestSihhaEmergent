import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Leaf, Mail, Send, ArrowLeft } from "lucide-react";
import { formatApiErrorDetail } from "./ResetPassword";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      {sent ? (
        <div data-testid="forgot-sent">
          <h1 className="text-2xl font-bold tracking-tight mb-2">Check your email</h1>
          <p className="text-sm text-ink-soft mb-6">
            If an account exists for <span className="font-semibold text-ink">{email}</span>, we've sent a link to
            choose a new password. It works once and expires in 1 hour.
          </p>
          <Link to="/auth" data-testid="forgot-back-to-signin" className="btn-outline">Back to sign in</Link>
        </div>
      ) : (
        <>
          <h1 className="text-2xl font-bold tracking-tight mb-1">Forgot your password?</h1>
          <p className="text-sm text-ink-soft mb-6">Enter your account email and we'll send you a reset link.</p>
          {error && <ErrorBox>{error}</ErrorBox>}
          <form onSubmit={submit} className="space-y-4">
            <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">Email</label>
            <div className="flex items-center gap-2 border border-line rounded-lg px-3 py-2.5 focus-within:ring-2 focus-within:ring-forest bg-white">
              <Mail className="h-4 w-4 text-ink-soft shrink-0" />
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="forgot-email-input" placeholder="you@example.com"
                className="w-full bg-transparent text-sm focus:outline-none" />
            </div>
            <button type="submit" disabled={submitting} data-testid="forgot-submit-btn" className="btn-primary w-full justify-center py-3">
              <Send className="h-4 w-4" /> {submitting ? "Sending…" : "Send reset link"}
            </button>
          </form>
          <Link to="/auth" data-testid="forgot-cancel-link" className="mt-5 inline-flex items-center gap-1 text-xs text-ink-soft underline">
            <ArrowLeft className="h-3 w-3" /> Back to sign in
          </Link>
        </>
      )}
    </AuthShell>
  );
}

export function AuthShell({ children }) {
  return (
    <div className="min-h-screen bg-sand flex items-center justify-center px-6">
      <div className="w-full max-w-md fade-up">
        <Link to="/" className="flex items-center justify-center gap-2 mb-8" data-testid="auth-shell-logo">
          <div className="h-10 w-10 rounded-full bg-forest flex items-center justify-center">
            <Leaf className="h-5 w-5 text-sage" />
          </div>
          <span className="font-heading font-bold text-2xl text-forest">Sihha AI</span>
        </Link>
        <div className="card p-8">{children}</div>
      </div>
    </div>
  );
}

export const ErrorBox = ({ children }) => (
  <div className="mb-4 border border-terracotta/40 bg-terracotta/5 text-terracotta text-sm rounded-xl px-4 py-3" data-testid="auth-error">
    {children}
  </div>
);

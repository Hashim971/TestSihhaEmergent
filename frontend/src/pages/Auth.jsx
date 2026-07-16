import React, { useState } from "react";
import { useNavigate, Navigate, Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Leaf, Mail, Lock, User, LogIn, UserPlus } from "lucide-react";

function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default function Auth() {
  const { user, loading, setUser } = useAuth();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const payload = mode === "login"
        ? { email: form.email, password: form.password }
        : { name: form.name, email: form.email, password: form.password };
      const { data } = await api.post(`/auth/${mode === "login" ? "login" : "register"}`, payload);
      setUser(data);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-sand flex items-center justify-center px-6">
      <div className="w-full max-w-md fade-up">
        <Link to="/" className="flex items-center justify-center gap-2 mb-8" data-testid="auth-logo-link">
          <div className="h-10 w-10 rounded-full bg-forest flex items-center justify-center">
            <Leaf className="h-5 w-5 text-sage" />
          </div>
          <span className="font-heading font-bold text-2xl text-forest">Sihha AI</span>
        </Link>

        <div className="card p-8">
          <div className="flex rounded-full border border-line p-1 mb-8 bg-sand">
            <button
              onClick={() => { setMode("login"); setError(null); }}
              data-testid="auth-tab-login"
              className={`flex-1 py-2 rounded-full text-sm font-medium ${mode === "login" ? "bg-forest text-white" : "text-ink-soft"}`}
              style={{ transition: "background-color 0.2s ease, color 0.2s ease" }}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode("register"); setError(null); }}
              data-testid="auth-tab-register"
              className={`flex-1 py-2 rounded-full text-sm font-medium ${mode === "register" ? "bg-forest text-white" : "text-ink-soft"}`}
              style={{ transition: "background-color 0.2s ease, color 0.2s ease" }}
            >
              Create Account
            </button>
          </div>

          <h1 className="text-2xl font-bold tracking-tight mb-1">
            {mode === "login" ? "Welcome back" : "Join Sihha AI"}
          </h1>
          <p className="text-sm text-ink-soft mb-6">
            {mode === "login" ? "Sign in to your health dashboard." : "Create your account to start managing your health."}
          </p>

          {error && (
            <div className="mb-4 border border-terracotta/40 bg-terracotta/5 text-terracotta text-sm rounded-xl px-4 py-3" data-testid="auth-error">
              {error}
            </div>
          )}

          <form onSubmit={submit} className="space-y-4">
            {mode === "register" && (
              <Field icon={User} label="Full name">
                <input
                  value={form.name} required
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  data-testid="auth-input-name"
                  placeholder="Jane Doe"
                  className="w-full bg-transparent text-sm focus:outline-none"
                />
              </Field>
            )}
            <Field icon={Mail} label="Email">
              <input
                type="email" value={form.email} required
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                data-testid="auth-input-email"
                placeholder="you@example.com"
                className="w-full bg-transparent text-sm focus:outline-none"
              />
            </Field>
            <Field icon={Lock} label="Password">
              <input
                type="password" value={form.password} required minLength={6}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                data-testid="auth-input-password"
                placeholder={mode === "register" ? "At least 6 characters" : "••••••••"}
                className="w-full bg-transparent text-sm focus:outline-none"
              />
            </Field>
            <button type="submit" disabled={submitting} data-testid="auth-submit-btn" className="btn-primary w-full justify-center py-3">
              {mode === "login" ? <LogIn className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
              {submitting ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>
        <p className="text-center text-xs text-ink-soft mt-6">
          Your data is stored securely and never shared without your consent.
        </p>
      </div>
    </div>
  );
}

function Field({ icon: Icon, label, children }) {
  return (
    <div>
      <label className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</label>
      <div className="mt-1 flex items-center gap-2 border border-line rounded-lg px-3 py-2.5 focus-within:ring-2 focus-within:ring-forest bg-white">
        <Icon className="h-4 w-4 text-ink-soft shrink-0" />
        {children}
      </div>
    </div>
  );
}

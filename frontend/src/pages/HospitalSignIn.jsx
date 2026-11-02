import React, { useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { LogIn, MapPin, Sparkles, Building2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { usePlatform } from "../context/PlatformContext";
import { LanguageToggle } from "../components/LanguageToggle";

const home = (role) => (role === "doctor" ? "/doctor" : "/dashboard");

export default function HospitalSignIn() {
  const { slug } = useParams();
  const { user, loading, setUser } = useAuth();
  const { loadTenant } = usePlatform();
  const navigate = useNavigate();
  const [tenant, setTenant] = useState(undefined);
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/tenant", { params: { slug } }).then(({ data }) => {
      setTenant(data.tenant);
      if (data.tenant) {
        sessionStorage.setItem("sihha_tenant_preview", data.tenant.account_id);
        loadTenant();
      }
    }).catch(() => setTenant(null));
  }, [slug, loadTenant]);

  if (!loading && user && tenant) return <Navigate to={home(user.role)} replace />;
  if (tenant === undefined) return <div className="min-h-screen bg-sand flex items-center justify-center text-sm text-ink-soft">Loading…</div>;
  if (!tenant) {
    return (
      <div className="min-h-screen bg-sand flex items-center justify-center px-6">
        <div className="card p-10 max-w-md text-center" data-testid="hospital-signin-missing">
          <Building2 className="h-9 w-9 text-forest mx-auto mb-3" />
          <h1 className="text-2xl font-bold tracking-tight">This hospital page isn't available</h1>
          <p className="text-sm text-ink-soft mt-2">Check the address, or sign in through Sihha AI instead.</p>
          <Link to="/auth" className="btn-primary mt-6 inline-flex" data-testid="hospital-signin-fallback">Go to Sihha AI sign-in</Link>
        </div>
      </div>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { data } = await api.post("/auth/login", form);
      if (data.account_id !== tenant.account_id && !data.is_admin) {
        await api.post("/auth/logout").catch(() => {});
        setError(`This account isn't registered with ${tenant.name}.`);
        return;
      }
      setUser(data);
      navigate(home(data.role), { replace: true });
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Sign-in failed. Check your email and password.");
    } finally {
      setBusy(false);
    }
  };

  const brand = tenant.primary_color || "#1F4D3A";
  const accent = tenant.accent_color || "#D9A441";
  const input = "mt-1 w-full border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2";
  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2" data-testid="hospital-signin">
      <aside className="relative overflow-hidden text-white px-8 sm:px-14 py-12 flex flex-col justify-between min-h-[320px]" style={{ background: brand }}>
        <div className="absolute -end-24 -top-24 h-72 w-72 rounded-full opacity-20" style={{ background: accent }} />
        <div className="absolute -start-16 bottom-10 h-40 w-40 rounded-full opacity-10 bg-white" />
        <div className="relative flex items-center gap-3">
          {tenant.logo_url
            ? <img src={`${process.env.REACT_APP_BACKEND_URL}${tenant.logo_url}`} alt="" className="h-12 w-12 rounded-xl object-cover bg-white" />
            : <span className="h-12 w-12 rounded-xl flex items-center justify-center text-xl font-bold" style={{ background: accent, color: brand }}>{tenant.name.charAt(0)}</span>}
          <span className="font-heading text-xl font-bold" data-testid="hospital-signin-name">{tenant.name}</span>
        </div>
        <div className="relative max-w-md fade-up">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight leading-tight">{tenant.tagline || "Your health, with your hospital."}</h1>
          {tenant.city && <p className="mt-4 text-white/80 flex items-center gap-2"><MapPin className="h-4 w-4" /> {tenant.city}</p>}
        </div>
        <p className="relative text-xs text-white/70">Powered by Sihha AI</p>
      </aside>

      <main className="bg-sand flex items-center justify-center px-6 py-12 relative">
        <div className="absolute top-4 end-4"><LanguageToggle testid="hospital-signin-language" /></div>
        <div className="w-full max-w-md">
          <form onSubmit={submit} className="card p-8 space-y-4" data-testid="hospital-signin-form">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">Sign in</h2>
              <p className="text-sm text-ink-soft mt-1">Patients and staff of {tenant.name}.</p>
            </div>
            {error && <div className="border border-terracotta/40 bg-terracotta/5 text-terracotta text-sm rounded-xl px-4 py-3" data-testid="hospital-signin-error">{error}</div>}
            <label className="block text-sm"><span className="text-xs uppercase tracking-[0.15em] text-ink-soft">Email</span>
              <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={input} style={{ "--tw-ring-color": brand }} data-testid="hospital-signin-email" /></label>
            <label className="block text-sm"><span className="text-xs uppercase tracking-[0.15em] text-ink-soft">Password</span>
              <input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={input} style={{ "--tw-ring-color": brand }} data-testid="hospital-signin-password" /></label>
            <button type="submit" disabled={busy} className="w-full rounded-full py-3 text-white font-semibold inline-flex items-center justify-center gap-2 disabled:opacity-60 hover:opacity-90"
              style={{ background: brand, transition: "opacity 0.2s ease" }} data-testid="hospital-signin-submit">
              <LogIn className="h-4 w-4" /> {busy ? "Signing in…" : "Sign In"}
            </button>
            <div className="flex justify-between text-xs">
              <Link to="/auth/forgot" className="underline text-ink-soft" data-testid="hospital-signin-forgot">Forgot password?</Link>
              <Link to={`/auth?tenant=${tenant.account_id}`} className="underline" style={{ color: brand }} data-testid="hospital-signin-register">New patient? Create an account</Link>
            </div>
          </form>
          {tenant.demo_logins.length > 0 && (
            <div className="card p-5 mt-4" data-testid="hospital-demo-logins">
              <p className="text-xs font-semibold flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" style={{ color: brand }} /> Demo accounts — tap to fill in</p>
              <div className="mt-3 grid gap-2">
                {tenant.demo_logins.map((d) => (
                  <button key={d.email} type="button" onClick={() => setForm({ email: d.email, password: d.password })} data-testid={`demo-login-${d.label.toLowerCase().replace(/\s+/g, "-")}`}
                    className="text-start rounded-xl border border-line bg-white px-3 py-2 hover:bg-sand text-sm" style={{ transition: "background-color 0.2s ease" }}>
                    <span className="font-semibold">{d.label}</span> <span className="text-xs text-ink-soft"><bdi>{d.email}</bdi> · <bdi>{d.password}</bdi></span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

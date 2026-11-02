import React, { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Store, LogIn, Send, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { BrandMark } from "../components/BrandMark";
import { LanguageToggle } from "../components/LanguageToggle";

const home = (role) => (role === "doctor" ? "/doctor" : role === "pharmacist" ? "/pharmacy-portal" : "/dashboard");
const detail = (e) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join(" ") : "Something went wrong. Please try again.";
};

export default function PharmacyAuth() {
  const { user, loading, setUser } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", name: "", pharmacy_name: "", city: "", sfda_license: "", phone: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [applied, setApplied] = useState(false);

  if (!loading && user) return <Navigate to={home(user.role)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "apply") {
        await api.post("/pharmacy-portal/apply", form);
        setApplied(true);
        return;
      }
      const { data } = await api.post("/auth/login", { email: form.email, password: form.password });
      if (data.role !== "pharmacist") {
        await api.post("/auth/logout").catch(() => {});
        setError("This isn't a pharmacy account. Use the patient or clinician sign-in instead.");
        return;
      }
      setUser(data);
      navigate("/pharmacy-portal", { replace: true });
    } catch (err) {
      setError(detail(err));
    } finally {
      setBusy(false);
    }
  };

  if (applied) {
    return (
      <div className="min-h-screen bg-sand flex items-center justify-center px-6">
        <div className="card p-10 max-w-md text-center fade-up" data-testid="pharmacy-application-sent">
          <CheckCircle2 className="h-10 w-10 text-forest mx-auto mb-3" />
          <h1 className="text-2xl font-bold tracking-tight mb-2">Application received</h1>
          <p className="text-sm text-ink-soft mb-6">We check your licence and approve the pharmacy. You'll get an email, then you can sign in here to manage orders.</p>
          <button onClick={() => { setApplied(false); setMode("login"); }} className="btn-outline" data-testid="application-back-btn">Back to sign in</button>
        </div>
      </div>
    );
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const input = "mt-1 w-full border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest";
  const F = ({ k, label, type = "text", ...rest }) => (
    <label className="block text-sm"><span className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</span>
      <input type={type} value={form[k]} onChange={set(k)} required className={input} data-testid={`pharmacy-auth-${k}`} {...rest} /></label>
  );

  return (
    <div className="min-h-screen bg-sand flex items-center justify-center px-6 py-10 relative">
      <div className="absolute top-4 end-4"><LanguageToggle testid="pharmacy-auth-language-toggle" /></div>
      <div className="w-full max-w-md fade-up">
        <Link to="/" className="flex items-center justify-center mb-8"><BrandMark size="lg" suffix=" for Pharmacies" testid="pharmacy-auth-brand" /></Link>
        <div className="card p-8" data-testid="pharmacy-auth-card">
          <div className="flex rounded-full border border-line p-1 mb-6 bg-sand">
            {[["login", "Sign In"], ["apply", "Join as a pharmacy"]].map(([k, label]) => (
              <button key={k} type="button" onClick={() => { setMode(k); setError(null); }} data-testid={`pharmacy-auth-tab-${k}`}
                className={`flex-1 py-2 rounded-full text-sm font-medium ${mode === k ? "bg-forest text-white" : "text-ink-soft"}`}>{label}</button>
            ))}
          </div>
          <h1 className="text-2xl font-bold tracking-tight mb-1 flex items-center gap-2"><Store className="h-5 w-5 text-forest" /> {mode === "login" ? "Pharmacy sign-in" : "Apply to the marketplace"}</h1>
          <p className="text-sm text-ink-soft mb-5">{mode === "login" ? "Manage prescription orders and your sponsored placement." : "We approve every pharmacy before it can receive orders."}</p>
          {error && <div className="mb-4 border border-terracotta/40 bg-terracotta/5 text-terracotta text-sm rounded-xl px-4 py-3" data-testid="pharmacy-auth-error">{error}</div>}
          <form onSubmit={submit} className="space-y-3">
            {mode === "apply" && (
              <>
                {F({ k: "pharmacy_name", label: "Pharmacy name" })}
                <div className="grid grid-cols-2 gap-3">
                  {F({ k: "city", label: "City" })}
                  {F({ k: "sfda_license", label: "SFDA licence no." })}
                </div>
                {F({ k: "name", label: "Your name" })}
                {F({ k: "phone", label: "Phone", required: false })}
              </>
            )}
            {F({ k: "email", label: "Email", type: "email" })}
            {F({ k: "password", label: "Password", type: "password", minLength: 6 })}
            <button type="submit" disabled={busy} className="btn-primary w-full justify-center py-3" data-testid="pharmacy-auth-submit">
              {mode === "login" ? <LogIn className="h-4 w-4" /> : <Send className="h-4 w-4" />}
              {busy ? "Please wait…" : mode === "login" ? "Sign In" : "Send application"}
            </button>
            {mode === "login" && <div className="text-end"><Link to="/auth/forgot" className="text-xs text-forest underline" data-testid="pharmacy-forgot-link">Forgot password?</Link></div>}
          </form>
        </div>
        <p className="text-center text-xs text-ink-soft mt-6"><Link to="/auth" className="underline" data-testid="pharmacy-to-patient-auth">Not a pharmacy? Sign in as a patient</Link></p>
      </div>
    </div>
  );
}

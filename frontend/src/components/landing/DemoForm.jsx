import React, { useState } from "react";
import { Send, CheckCircle2 } from "lucide-react";
import { api } from "../../lib/api";

const field = "w-full rounded-lg bg-white/10 border border-white/20 px-4 py-3 text-sm text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-sage focus:border-sage";

export function DemoForm() {
  const [form, setForm] = useState({ name: "", email: "", organization: "", role: "", message: "" });
  const [state, setState] = useState("idle");
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setState("sending");
    setError("");
    try {
      await api.post("/demo-requests", { ...form, role: form.role || null, message: form.message || null });
      setState("sent");
    } catch (err) {
      const d = err.response?.data?.detail;
      setError(typeof d === "string" ? d : "Please check the form and try again.");
      setState("idle");
    }
  };

  if (state === "sent") {
    return (
      <div className="rounded-2xl bg-white/10 border border-white/20 p-8 flex flex-col items-start gap-3" data-testid="demo-form-sent">
        <CheckCircle2 className="h-8 w-8 text-sage" />
        <p className="text-xl font-semibold">Thanks, {form.name.split(" ")[0]}.</p>
        <p className="text-white/70 text-sm">We'll reach out at {form.email} to schedule your demo.</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="rounded-2xl bg-white/5 border border-white/15 p-6 sm:p-8 grid grid-cols-1 sm:grid-cols-2 gap-4" data-testid="demo-form">
      <input required minLength={2} placeholder="Full name" value={form.name} onChange={set("name")} data-testid="demo-name-input" className={field} />
      <input required type="email" placeholder="Work email" value={form.email} onChange={set("email")} data-testid="demo-email-input" className={field} />
      <input required minLength={2} placeholder="Hospital or organisation" value={form.organization} onChange={set("organization")} data-testid="demo-org-input" className={field} />
      <input placeholder="Your role" value={form.role} onChange={set("role")} data-testid="demo-role-input" className={field} />
      <textarea rows={3} placeholder="What would you like to see?" value={form.message} onChange={set("message")} data-testid="demo-message-input" className={`${field} sm:col-span-2`} />
      {error && <p className="sm:col-span-2 text-sm text-amber-200" data-testid="demo-form-error">{error}</p>}
      <button disabled={state === "sending"} data-testid="demo-submit-btn"
        className="sm:col-span-2 inline-flex items-center justify-center gap-2 rounded-full bg-white text-forest font-semibold px-6 py-3 hover:bg-sage disabled:opacity-60" style={{ transition: "background-color 0.2s ease" }}>
        <Send className="h-4 w-4" /> {state === "sending" ? "Sending…" : "Request a demo"}
      </button>
    </form>
  );
}

import React, { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import YesNo from "../components/YesNo";
import { Save, User, HeartPulse, Pill, Leaf } from "lucide-react";

const EMPTY = {
  height: "", height_unit: "cm", weight: "", weight_unit: "kg",
  date_of_birth: "", calendar: "gregorian",
  chronic_conditions: false, chronic_conditions_details: "",
  family_history: false, family_history_details: "",
  allergies: false, allergies_details: "",
  surgical_history: false, surgical_history_details: "",
  current_medications: false, current_medications_details: "",
  recent_medications: false, recent_medications_details: "",
  smoker: false,
  dietary_habits: false, dietary_habits_details: "",
  physical_activity: false, physical_activity_details: "",
  sleep_pattern: false, sleep_pattern_details: "",
  stress_level: false, stress_level_details: "",
};

export default function Settings() {
  const { user, setUser } = useAuth();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(() => {
    const hp = user.health_profile || {};
    const merged = { ...EMPTY };
    Object.keys(EMPTY).forEach((k) => {
      if (hp[k] !== undefined && hp[k] !== null) merged[k] = hp[k];
    });
    return merged;
  });

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        ...form,
        height: form.height === "" ? null : parseFloat(form.height),
        weight: form.weight === "" ? null : parseFloat(form.weight),
        date_of_birth: form.date_of_birth || null,
      };
      const { data } = await api.put("/profile/health", payload);
      setUser(data);
      toast.success("Health profile updated — your AI assistant will use the new information.");
    } catch {
      toast.error("Could not save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-8 fade-up" data-testid="settings-page">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-ink-soft mt-1">Your health profile personalizes the AI assistant and screening reports.</p>
        </div>
        <button onClick={save} disabled={saving} data-testid="settings-save-btn" className="btn-primary">
          <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save Changes"}
        </button>
      </div>

      <div className="card p-6 flex items-center gap-4" data-testid="settings-account-card">
        <span className="h-12 w-12 rounded-full bg-sage text-forest flex items-center justify-center text-lg font-bold font-heading">
          {user.name?.charAt(0).toUpperCase()}
        </span>
        <div>
          <p className="font-semibold">{user.name}</p>
          <p className="text-sm text-ink-soft">{user.email} · {user.role}</p>
        </div>
      </div>

      <Section icon={User} title="General Information">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-sm font-medium">Height</label>
            <div className="mt-1 flex">
              <input type="number" step="any" value={form.height} onChange={(e) => set("height", e.target.value)}
                data-testid="settings-input-height"
                className="flex-1 w-full border border-line rounded-l-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
              <select value={form.height_unit} onChange={(e) => set("height_unit", e.target.value)}
                className="border border-l-0 border-line rounded-r-lg px-3 py-2.5 text-sm bg-white focus:outline-none">
                <option value="cm">cm</option><option value="ft">ft</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Weight</label>
            <div className="mt-1 flex">
              <input type="number" step="any" value={form.weight} onChange={(e) => set("weight", e.target.value)}
                data-testid="settings-input-weight"
                className="flex-1 w-full border border-line rounded-l-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
              <select value={form.weight_unit} onChange={(e) => set("weight_unit", e.target.value)}
                className="border border-l-0 border-line rounded-r-lg px-3 py-2.5 text-sm bg-white focus:outline-none">
                <option value="kg">kg</option><option value="lb">lb</option>
              </select>
            </div>
          </div>
        </div>
        <div className="mt-6">
          <label className="text-sm font-medium">Date of Birth</label>
          <div className="mt-1 flex flex-col md:flex-row md:items-center gap-4">
            {form.calendar === "gregorian" ? (
              <input type="date" value={form.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)}
                data-testid="settings-input-dob"
                className="flex-1 border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
            ) : (
              <input type="text" value={form.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)}
                placeholder="e.g. 1419-05-12 AH" data-testid="settings-input-dob-hijri"
                className="flex-1 border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
            )}
            <div className="flex items-center gap-4">
              {["gregorian", "hijri"].map((c) => (
                <label key={c} className="flex items-center gap-1.5 text-sm cursor-pointer">
                  <input type="radio" name="settings-calendar" checked={form.calendar === c}
                    onChange={() => { set("calendar", c); set("date_of_birth", ""); }}
                    className="accent-[#1E3F2A]" />
                  {c === "gregorian" ? "Gregorian" : "Hijri"}
                </label>
              ))}
            </div>
          </div>
        </div>
      </Section>

      <Section icon={HeartPulse} title="Health History">
        <div className="space-y-8">
          <YesNo label="Chronic and Past Health Conditions"
            desc="Include any chronic conditions or medical issues experienced."
            value={form.chronic_conditions} onChange={(v) => set("chronic_conditions", v)}
            details={form.chronic_conditions_details} onDetails={(v) => set("chronic_conditions_details", v)}
            placeholder="e.g. Type 2 diabetes, hypertension…" testid="settings-chronic" />
          <YesNo label="Family Health History"
            desc="The family's health history can indicate genetic risks."
            value={form.family_history} onChange={(v) => set("family_history", v)}
            details={form.family_history_details} onDetails={(v) => set("family_history_details", v)}
            placeholder="e.g. Father: heart disease…" testid="settings-family" />
          <YesNo label="Allergies"
            desc="Do you suffer from allergies to foods, medications, or other things?"
            value={form.allergies} onChange={(v) => set("allergies", v)}
            details={form.allergies_details} onDetails={(v) => set("allergies_details", v)}
            placeholder="e.g. Penicillin, peanuts…" testid="settings-allergies" />
          <YesNo label="Surgical History"
            desc="Include any surgical procedures done."
            value={form.surgical_history} onChange={(v) => set("surgical_history", v)}
            details={form.surgical_history_details} onDetails={(v) => set("surgical_history_details", v)}
            placeholder="e.g. Appendectomy (2019)…" testid="settings-surgical" />
        </div>
      </Section>

      <Section icon={Pill} title="Medications">
        <div className="space-y-8">
          <YesNo label="Current Medications"
            desc="Medications that are taken on daily bases."
            value={form.current_medications} onChange={(v) => set("current_medications", v)}
            details={form.current_medications_details} onDetails={(v) => set("current_medications_details", v)}
            placeholder="e.g. Metformin 500mg twice daily…" testid="settings-current-meds" />
          <YesNo label="Medications Taken in the Last 6 Months"
            desc="Such as antibiotics, pain relievers, antihistamines, or other medications."
            value={form.recent_medications} onChange={(v) => set("recent_medications", v)}
            details={form.recent_medications_details} onDetails={(v) => set("recent_medications_details", v)}
            placeholder="e.g. Amoxicillin course in March…" testid="settings-recent-meds" />
        </div>
      </Section>

      <Section icon={Leaf} title="Lifestyle Information">
        <div className="space-y-8">
          <YesNo label="Do You Smoke?" value={form.smoker} onChange={(v) => set("smoker", v)} testid="settings-smoker" />
          <YesNo label="Dietary Habits" desc="Do you follow any specific dietary habits?"
            value={form.dietary_habits} onChange={(v) => set("dietary_habits", v)}
            details={form.dietary_habits_details} onDetails={(v) => set("dietary_habits_details", v)}
            placeholder="e.g. Low-carb, intermittent fasting…" testid="settings-diet" />
          <YesNo label="Weekly Physical Activity Level" desc="Indicate the average level of physical activity performed each week."
            value={form.physical_activity} onChange={(v) => set("physical_activity", v)}
            details={form.physical_activity_details} onDetails={(v) => set("physical_activity_details", v)}
            placeholder="e.g. Gym 3x per week, daily walks…" testid="settings-activity" />
          <YesNo label="Daily Sleep Pattern" desc="Indicate your typical sleep pattern each day."
            value={form.sleep_pattern} onChange={(v) => set("sleep_pattern", v)}
            details={form.sleep_pattern_details} onDetails={(v) => set("sleep_pattern_details", v)}
            placeholder="e.g. 6-7 hours, trouble falling asleep…" testid="settings-sleep" />
          <YesNo label="Stress Level" desc="Indicate your average level of stress experienced."
            value={form.stress_level} onChange={(v) => set("stress_level", v)}
            details={form.stress_level_details} onDetails={(v) => set("stress_level_details", v)}
            placeholder="e.g. High work stress lately…" testid="settings-stress" />
        </div>
      </Section>

      <div className="flex justify-end">
        <button onClick={save} disabled={saving} data-testid="settings-save-btn-bottom" className="btn-primary">
          <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </div>
  );
}

function Section({ icon: Icon, title, children }) {
  return (
    <div className="card p-8">
      <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
        <Icon className="h-5 w-5 text-forest" /> {title}
      </h2>
      {children}
    </div>
  );
}

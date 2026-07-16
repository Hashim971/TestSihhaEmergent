import React, { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Leaf, Check, ChevronLeft, ChevronRight, Activity } from "lucide-react";

const STEPS = ["Account", "General", "Health History", "Medications", "Lifestyle"];

export default function Onboarding() {
  const { user, loading, setUser } = useAuth();
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const [form, setForm] = useState({
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
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-sand">
        <Activity className="h-8 w-8 text-forest animate-pulse" />
      </div>
    );
  }
  if (!user) return <Navigate to="/auth" replace />;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async (skip = false) => {
    setSubmitting(true);
    try {
      const payload = skip ? { skip: true } : {
        ...form,
        height: form.height === "" ? null : parseFloat(form.height),
        weight: form.weight === "" ? null : parseFloat(form.weight),
        date_of_birth: form.date_of_birth || null,
      };
      const { data } = await api.put("/profile/health", payload);
      setUser(data);
      toast.success(skip ? "You can complete your health profile anytime." : "Health profile saved — your AI assistant will use it.");
      navigate("/dashboard", { replace: true });
    } catch {
      toast.error("Could not save your profile. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-sand py-10 px-6" data-testid="onboarding-page">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-center gap-2 mb-10">
          <div className="h-9 w-9 rounded-full bg-forest flex items-center justify-center">
            <Leaf className="h-5 w-5 text-sage" />
          </div>
          <span className="font-heading font-bold text-xl text-forest">Sihha AI</span>
        </div>

        {/* Step indicator */}
        <div className="flex items-center justify-center mb-10" data-testid="onboarding-steps">
          {STEPS.map((label, i) => (
            <React.Fragment key={label}>
              <div className="flex flex-col items-center">
                <div className={`h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold ${
                  i < step ? "bg-forest text-white" : i === step ? "bg-forest text-white ring-4 ring-sage/50" : "bg-line text-ink-soft"
                }`} style={{ transition: "background-color 0.2s ease" }}>
                  {i < step ? <Check className="h-5 w-5" /> : i + 1}
                </div>
                <span className="text-[10px] uppercase tracking-wider text-ink-soft mt-2 hidden sm:block">{label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`h-0.5 w-10 sm:w-16 mx-1 sm:-mt-5 ${i < step ? "bg-forest" : "bg-line"}`} />
              )}
            </React.Fragment>
          ))}
        </div>

        <div className="card p-8 md:p-10 fade-up" key={step}>
          {step === 1 && (
            <StepCard
              title="General Information"
              subtitle="By providing general information about you we'll make sure your experience will be completely tailored to your needs."
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="text-sm font-medium">Height</label>
                  <div className="mt-1 flex">
                    <input type="number" step="any" value={form.height} onChange={(e) => set("height", e.target.value)}
                      data-testid="onboarding-input-height" placeholder="179"
                      className="flex-1 border border-line rounded-l-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
                    <select value={form.height_unit} onChange={(e) => set("height_unit", e.target.value)}
                      data-testid="onboarding-select-height-unit"
                      className="border border-l-0 border-line rounded-r-lg px-3 py-2.5 text-sm bg-white focus:outline-none">
                      <option value="cm">cm</option>
                      <option value="ft">ft</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">Weight</label>
                  <div className="mt-1 flex">
                    <input type="number" step="any" value={form.weight} onChange={(e) => set("weight", e.target.value)}
                      data-testid="onboarding-input-weight" placeholder="80"
                      className="flex-1 border border-line rounded-l-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
                    <select value={form.weight_unit} onChange={(e) => set("weight_unit", e.target.value)}
                      data-testid="onboarding-select-weight-unit"
                      className="border border-l-0 border-line rounded-r-lg px-3 py-2.5 text-sm bg-white focus:outline-none">
                      <option value="kg">kg</option>
                      <option value="lb">lb</option>
                    </select>
                  </div>
                </div>
              </div>
              <div className="mt-6">
                <label className="text-sm font-medium">Date of Birth</label>
                <div className="mt-1 flex flex-col md:flex-row md:items-center gap-4">
                  {form.calendar === "gregorian" ? (
                    <input type="date" value={form.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)}
                      data-testid="onboarding-input-dob"
                      className="flex-1 border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
                  ) : (
                    <input type="text" value={form.date_of_birth} onChange={(e) => set("date_of_birth", e.target.value)}
                      data-testid="onboarding-input-dob-hijri" placeholder="e.g. 1419-05-12 AH"
                      className="flex-1 border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
                  )}
                  <div className="flex items-center gap-4">
                    {["gregorian", "hijri"].map((c) => (
                      <label key={c} className="flex items-center gap-1.5 text-sm cursor-pointer" data-testid={`onboarding-calendar-${c}`}>
                        <input type="radio" name="calendar" checked={form.calendar === c}
                          onChange={() => { set("calendar", c); set("date_of_birth", ""); }}
                          className="accent-[#1E3F2A]" />
                        {c === "gregorian" ? "Gregorian" : "Hijri"}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </StepCard>
          )}

          {step === 2 && (
            <StepCard title="Health History">
              <YesNo label="Chronic and Past Health Conditions"
                desc="Include any chronic conditions or medical issues experienced. Essential for understanding health history and personalized care."
                value={form.chronic_conditions} onChange={(v) => set("chronic_conditions", v)}
                details={form.chronic_conditions_details} onDetails={(v) => set("chronic_conditions_details", v)}
                placeholder="e.g. Type 2 diabetes, hypertension…" testid="chronic" />
              <YesNo label="Family Health History"
                desc="The family's health history can indicate genetic risks. Knowing this helps us predict and prevent potential health issues."
                value={form.family_history} onChange={(v) => set("family_history", v)}
                details={form.family_history_details} onDetails={(v) => set("family_history_details", v)}
                placeholder="e.g. Father: heart disease…" testid="family" />
              <YesNo label="Allergies"
                desc="Do you suffer from allergies to foods, medications, or other things?"
                value={form.allergies} onChange={(v) => set("allergies", v)}
                details={form.allergies_details} onDetails={(v) => set("allergies_details", v)}
                placeholder="e.g. Penicillin, peanuts…" testid="allergies" />
              <YesNo label="Surgical History"
                desc="Include any surgical procedures done."
                value={form.surgical_history} onChange={(v) => set("surgical_history", v)}
                details={form.surgical_history_details} onDetails={(v) => set("surgical_history_details", v)}
                placeholder="e.g. Appendectomy (2019)…" testid="surgical" />
            </StepCard>
          )}

          {step === 3 && (
            <StepCard title="Medications">
              <YesNo label="Current Medications"
                desc="Medications that are taken on daily bases."
                value={form.current_medications} onChange={(v) => set("current_medications", v)}
                details={form.current_medications_details} onDetails={(v) => set("current_medications_details", v)}
                placeholder="e.g. Metformin 500mg twice daily…" testid="current-meds" />
              <YesNo label="Medications Taken in the Last 6 Months"
                desc="Such as antibiotics, pain relievers, antihistamines, or other medications."
                value={form.recent_medications} onChange={(v) => set("recent_medications", v)}
                details={form.recent_medications_details} onDetails={(v) => set("recent_medications_details", v)}
                placeholder="e.g. Amoxicillin course in March…" testid="recent-meds" />
            </StepCard>
          )}

          {step === 4 && (
            <StepCard title="Lifestyle Information">
              <YesNo label="Do You Smoke?" value={form.smoker} onChange={(v) => set("smoker", v)} testid="smoker" />
              <YesNo label="Dietary Habits" desc="Do you follow any specific dietary habits?"
                value={form.dietary_habits} onChange={(v) => set("dietary_habits", v)}
                details={form.dietary_habits_details} onDetails={(v) => set("dietary_habits_details", v)}
                placeholder="e.g. Low-carb, intermittent fasting…" testid="diet" />
              <YesNo label="Weekly Physical Activity Level" desc="Indicate the average level of physical activity performed each week."
                value={form.physical_activity} onChange={(v) => set("physical_activity", v)}
                details={form.physical_activity_details} onDetails={(v) => set("physical_activity_details", v)}
                placeholder="e.g. Gym 3x per week, daily walks…" testid="activity" />
              <YesNo label="Daily Sleep Pattern" desc="Indicate your typical sleep pattern each day."
                value={form.sleep_pattern} onChange={(v) => set("sleep_pattern", v)}
                details={form.sleep_pattern_details} onDetails={(v) => set("sleep_pattern_details", v)}
                placeholder="e.g. 6-7 hours, trouble falling asleep…" testid="sleep" />
              <YesNo label="Stress Level" desc="Indicate your average level of stress experienced."
                value={form.stress_level} onChange={(v) => set("stress_level", v)}
                details={form.stress_level_details} onDetails={(v) => set("stress_level_details", v)}
                placeholder="e.g. High work stress lately…" testid="stress" />
            </StepCard>
          )}

          <div className="flex items-center justify-between mt-10">
            {step > 1 ? (
              <button onClick={() => setStep(step - 1)} data-testid="onboarding-back-btn" className="btn-outline">
                <ChevronLeft className="h-4 w-4" /> Back
              </button>
            ) : <span />}
            {step < 4 ? (
              <button onClick={() => setStep(step + 1)} data-testid="onboarding-next-btn" className="btn-primary">
                Next <ChevronRight className="h-4 w-4" />
              </button>
            ) : (
              <button onClick={() => save(false)} disabled={submitting} data-testid="onboarding-complete-btn" className="btn-primary">
                <Check className="h-4 w-4" /> {submitting ? "Saving…" : "Complete"}
              </button>
            )}
          </div>
        </div>

        <p className="text-center mt-6">
          <button onClick={() => save(true)} disabled={submitting} data-testid="onboarding-skip-btn"
            className="text-sm text-ink-soft underline underline-offset-4 hover:text-ink" style={{ transition: "color 0.2s ease" }}>
            Skip for now — I'll fill this in later
          </button>
        </p>
      </div>
    </div>
  );
}

function StepCard({ title, subtitle, children }) {
  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight mb-2">{title}</h1>
      {subtitle && <p className="text-ink-soft leading-relaxed mb-8">{subtitle}</p>}
      {!subtitle && <div className="mb-8" />}
      <div className="space-y-8">{children}</div>
    </div>
  );
}

function YesNo({ label, desc, value, onChange, details, onDetails, placeholder, testid }) {
  return (
    <div>
      <p className="font-semibold">{label}</p>
      {desc && <p className="text-sm text-ink-soft mt-1 leading-relaxed">{desc}</p>}
      <div className="flex gap-3 mt-3">
        {[["Yes", true], ["No", false]].map(([txt, val]) => (
          <button key={txt} type="button" onClick={() => onChange(val)}
            data-testid={`onboarding-${testid}-${txt.toLowerCase()}`}
            className={`px-8 py-2 rounded-full text-sm font-medium border ${
              value === val ? "bg-forest text-white border-forest" : "bg-sand text-ink-soft border-line hover:bg-white"
            }`}
            style={{ transition: "background-color 0.2s ease, color 0.2s ease" }}>
            {txt}
          </button>
        ))}
      </div>
      {value === true && onDetails && (
        <textarea value={details} onChange={(e) => onDetails(e.target.value)} placeholder={placeholder}
          data-testid={`onboarding-${testid}-details`} rows={2}
          className="mt-3 w-full border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
      )}
    </div>
  );
}

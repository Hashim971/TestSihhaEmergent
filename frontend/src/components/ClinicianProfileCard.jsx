import React, { useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Stethoscope } from "lucide-react";

export function ClinicianProfileCard() {
  const { user, setUser } = useAuth();
  const [form, setForm] = useState({
    specialty: user.specialty || "",
    clinic: user.clinic || "",
    city: user.city || "",
    bio: user.bio || "",
  });
  const [saving, setSaving] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.put("/profile/clinician", form);
      setUser(data);
      toast.success("Your clinician profile is updated — patients see this when choosing a doctor.");
    } catch {
      toast.error("Could not save your profile");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="card p-8" data-testid="clinician-profile-card">
      <h2 className="text-xl font-semibold mb-2 flex items-center gap-2">
        <Stethoscope className="h-5 w-5 text-forest" /> Clinician Profile
      </h2>
      <p className="text-sm text-ink-soft mb-6">
        Patients see this when they choose their doctor. Keep it short and specific.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { key: "specialty", label: "Specialty", placeholder: "e.g. Cardiology" },
          { key: "clinic", label: "Clinic", placeholder: "e.g. Al Noor Medical Centre" },
          { key: "city", label: "City", placeholder: "e.g. Riyadh" },
        ].map(({ key, label, placeholder }) => (
          <label key={key} className="text-sm">
            <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">{label}</span>
            <input
              value={form[key]} placeholder={placeholder} data-testid={`clinician-${key}-input`}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              className="mt-1 w-full border border-line rounded-lg px-3 py-2.5 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-forest"
            />
          </label>
        ))}
      </div>
      <label className="text-sm block mt-4">
        <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">About</span>
        <textarea
          value={form.bio} rows={3} data-testid="clinician-bio-input"
          placeholder="One or two lines patients will read."
          onChange={(e) => setForm({ ...form, bio: e.target.value })}
          className="mt-1 w-full border border-line rounded-lg px-3 py-2.5 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-forest"
        />
      </label>
      <button type="submit" disabled={saving} data-testid="save-clinician-profile-btn" className="btn-primary mt-5">
        {saving ? "Saving…" : "Save Profile"}
      </button>
    </form>
  );
}

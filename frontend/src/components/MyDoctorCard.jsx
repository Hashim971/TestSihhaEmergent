import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Stethoscope, Search, Check, MapPin, PhoneCall } from "lucide-react";

export function MyDoctorCard() {
  const { user, setUser } = useAuth();
  const [doctors, setDoctors] = useState(null);
  const [filters, setFilters] = useState({ specialty: "", city: "" });
  const [saving, setSaving] = useState(false);
  const selected = user.assigned_doctor_user_id || "";

  const load = (specialty = "", city = "") => {
    setDoctors(null);
    api.get("/doctors", { params: { specialty: specialty || undefined, city: city || undefined } })
      .then(({ data }) => setDoctors(data)).catch(() => setDoctors([]));
  };

  useEffect(() => { load(); }, []);

  const choose = async (doctorId) => {
    setSaving(true);
    try {
      const { data } = await api.put("/profile/doctor", { doctor_user_id: doctorId || null });
      setUser(data);
      toast.success(doctorId ? "Your doctor has been updated." : "You no longer have an assigned doctor.");
    } catch {
      toast.error("Could not update your doctor. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card p-8" data-testid="my-doctor-card">
      <h2 className="text-xl font-semibold mb-2 flex items-center gap-2">
        <Stethoscope className="h-5 w-5 text-forest" /> My Doctor
      </h2>
      <p className="text-sm text-ink-soft mb-5">
        Only the doctor you choose here can open your record. Choosing a new doctor transfers your care —
        the previous doctor loses access immediately.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-5">
        <input value={filters.specialty} data-testid="doctor-filter-specialty"
          onChange={(e) => setFilters({ ...filters, specialty: e.target.value })}
          placeholder="Specialty (e.g. Cardiology)"
          className="border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest" />
        <input value={filters.city} data-testid="doctor-filter-city"
          onChange={(e) => setFilters({ ...filters, city: e.target.value })} placeholder="City (e.g. Riyadh)"
          className="border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest" />
        <button onClick={() => load(filters.specialty, filters.city)} className="btn-outline"
          data-testid="doctor-filter-btn">
          <Search className="h-4 w-4" /> Filter
        </button>
      </div>

      {doctors === null && <p className="text-sm text-ink-soft">Loading clinicians…</p>}
      {doctors?.length === 0 && (
        <p className="text-sm text-ink-soft" data-testid="no-doctors-found">
          No clinician matches that filter. Clear it to see everyone.
        </p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {(doctors || []).map((d) => {
          const mine = d.user_id === selected;
          return (
            <div key={d.user_id} data-testid={`doctor-card-${d.user_id}`}
              className={`border rounded-xl p-4 transition-colors ${
                mine ? "border-forest bg-sage/10" : "border-line hover:border-sage"}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-sm">{d.name}</p>
                  <p className="text-xs text-ink-soft mt-0.5">{d.specialty || "General practice"}</p>
                </div>
                {mine && (
                  <span className="text-[10px] uppercase tracking-wider bg-forest text-white px-2 py-0.5 rounded-full flex items-center gap-1"
                    data-testid={`current-doctor-${d.user_id}`}>
                    <Check className="h-3 w-3" /> Yours
                  </span>
                )}
              </div>
              {(d.clinic || d.city) && (
                <p className="text-xs text-ink-soft mt-2 flex items-center gap-1.5">
                  <MapPin className="h-3 w-3" /> {[d.clinic, d.city].filter(Boolean).join(" · ")}
                </p>
              )}
              {d.clinic_phone && (
                <a href={`tel:${d.clinic_phone}`} className="text-xs text-forest mt-1 inline-flex items-center gap-1">
                  <PhoneCall className="h-3 w-3" /> {d.clinic_phone}
                </a>
              )}
              {d.bio && <p className="text-xs mt-2 leading-relaxed">{d.bio}</p>}
              <button onClick={() => choose(mine ? "" : d.user_id)} disabled={saving}
                data-testid={`choose-doctor-${d.user_id}`}
                className={`mt-3 w-full justify-center ${mine ? "btn-outline" : "btn-primary"} !py-1.5 text-xs`}>
                {mine ? "Remove as my doctor" : "Choose this doctor"}
              </button>
            </div>
          );
        })}
      </div>

      {!user.sharing_enabled && (
        <p className="text-xs text-terracotta mt-4" data-testid="my-doctor-sharing-warning">
          Sharing is currently off, so your doctor cannot see your data. Turn on "Share with Doctors" in the sidebar.
        </p>
      )}
    </div>
  );
}

import React, { useState, useEffect } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Stethoscope } from "lucide-react";

export function MyDoctorCard() {
  const { user, setUser } = useAuth();
  const [doctors, setDoctors] = useState([]);
  const [loadError, setLoadError] = useState(false);
  const [selected, setSelected] = useState(user.assigned_doctor_user_id || "");
  const [saving, setSaving] = useState(false);

  const loadDoctors = () =>
    api.get("/doctors").then((r) => { setDoctors(r.data); setLoadError(false); }).catch(() => setLoadError(true));

  useEffect(() => { loadDoctors(); }, []);

  const save = async (doctorId) => {
    setSelected(doctorId);
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
      <select
        value={selected}
        disabled={saving}
        data-testid="my-doctor-select"
        onChange={(e) => save(e.target.value)}
        className="w-full md:w-2/3 border border-line rounded-lg px-3 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-forest"
      >
        <option value="">No doctor chosen</option>
        {doctors.map((d) => (
          <option key={d.user_id} value={d.user_id}>{d.name} — {d.email}</option>
        ))}
      </select>
      {loadError && (
        <button onClick={loadDoctors} data-testid="retry-doctors-btn" className="btn-outline mt-3">
          Could not load doctors — try again
        </button>
      )}
      {!user.sharing_enabled && (
        <p className="text-xs text-terracotta mt-3" data-testid="my-doctor-sharing-warning">
          Sharing is currently off, so your doctor cannot see your data. Turn on "Share with Doctors" in the sidebar.
        </p>
      )}
    </div>
  );
}

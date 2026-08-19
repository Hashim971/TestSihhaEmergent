import React, { useState, useEffect } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { ShieldCheck, UserCheck, AlertTriangle } from "lucide-react";

export default function AdminAssignments() {
  const { user } = useAuth();
  const [patients, setPatients] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);

  const load = async () => {
    try {
      const [p, d] = await Promise.all([api.get("/admin/patients"), api.get("/doctors")]);
      setPatients(p.data);
      setDoctors(d.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user.is_admin) load().catch(() => toast.error("Could not load assignments"));
  }, [user.is_admin]);

  const assign = async (patientId, doctorId) => {
    setSavingId(patientId);
    try {
      await api.put(`/admin/patients/${patientId}/doctor`, { doctor_user_id: doctorId || null });
      setPatients((list) =>
        list.map((p) =>
          p.user_id === patientId
            ? {
                ...p,
                assigned_doctor_user_id: doctorId || null,
                assigned_doctor_name: doctors.find((d) => d.user_id === doctorId)?.name || null,
                assigned_by: doctorId ? "admin" : null,
              }
            : p
        )
      );
      toast.success(doctorId ? "Patient assigned" : "Assignment cleared");
    } catch {
      toast.error("Could not update assignment");
    } finally {
      setSavingId(null);
    }
  };

  if (!user.is_admin) {
    return (
      <div className="card p-10 text-center max-w-lg mx-auto fade-up" data-testid="admin-access-denied">
        <ShieldCheck className="h-10 w-10 text-sage mx-auto mb-3" />
        <p className="text-ink-soft">Admin access required.</p>
      </div>
    );
  }

  const unassigned = patients.filter((p) => !p.assigned_doctor_user_id);

  return (
    <div className="space-y-8 fade-up" data-testid="admin-assignments-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
          <UserCheck className="h-7 w-7 text-forest" /> Patient Assignments
        </h1>
        <p className="text-ink-soft mt-1">
          Patients pick their own doctor in Settings. Anyone who hasn't chosen needs assigning here.
        </p>
      </div>

      {unassigned.length > 0 && (
        <div className="border border-terracotta/40 bg-terracotta/5 rounded-xl px-4 py-3 flex items-start gap-2"
          data-testid="unassigned-banner">
          <AlertTriangle className="h-4 w-4 text-terracotta mt-0.5" />
          <p className="text-xs text-ink">
            {unassigned.length} patient{unassigned.length === 1 ? "" : "s"} have no doctor and are not visible in any
            doctor's panel.
          </p>
        </div>
      )}

      <div className="card overflow-hidden" data-testid="assignments-table">
        <div className="hidden md:grid grid-cols-12 gap-4 px-6 py-3 border-b border-line text-[10px] uppercase tracking-[0.15em] text-ink-soft">
          <span className="col-span-4">Patient</span>
          <span className="col-span-2">Sharing</span>
          <span className="col-span-2">Chosen by</span>
          <span className="col-span-4">Assigned doctor</span>
        </div>
        {loading && <p className="px-6 py-6 text-sm text-ink-soft">Loading patients…</p>}
        {!loading && patients.length === 0 && (
          <p className="px-6 py-6 text-sm text-ink-soft">No patient accounts yet.</p>
        )}
        {patients.map((p) => (
          <div key={p.user_id}
            className="grid grid-cols-1 md:grid-cols-12 gap-3 md:gap-4 px-6 py-4 border-b border-line last:border-0 items-center"
            data-testid={`assignment-row-${p.user_id}`}>
            <div className="col-span-4 min-w-0">
              <p className="font-medium text-sm truncate">{p.name}</p>
              <p className="text-xs text-ink-soft truncate">{p.email}</p>
            </div>
            <span className={`col-span-2 text-[10px] uppercase tracking-wider font-bold ${
              p.sharing_enabled ? "text-forest" : "text-terracotta"}`}>
              {p.sharing_enabled ? "On" : "Off"}
            </span>
            <span className="col-span-2 text-xs text-ink-soft">{p.assigned_by || "—"}</span>
            <div className="col-span-4">
              <select
                value={p.assigned_doctor_user_id || ""}
                disabled={savingId === p.user_id}
                data-testid={`assign-doctor-select-${p.user_id}`}
                onChange={(e) => assign(p.user_id, e.target.value)}
                className="w-full border border-line rounded-lg px-3 py-2 text-sm bg-white"
              >
                <option value="">Unassigned</option>
                {doctors.map((d) => (
                  <option key={d.user_id} value={d.user_id}>{d.name}</option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

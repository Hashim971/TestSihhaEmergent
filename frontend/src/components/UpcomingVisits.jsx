import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { CalendarClock, CalendarX, PhoneCall, RefreshCw } from "lucide-react";

export function UpcomingVisits({ reloadKey }) {
  const [visits, setVisits] = useState(null);
  const [rescheduling, setRescheduling] = useState(null);
  const [slots, setSlots] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get("/my-visits")
    .then(({ data }) => setVisits(data.upcoming)).catch(() => setVisits([])), []);

  useEffect(() => { load(); }, [load, reloadKey]);

  const openReschedule = async (visit) => {
    setRescheduling(visit.encounter_id);
    const { data } = await api.get("/booking/slots", { params: { doctor_user_id: visit.doctor_user_id } });
    setSlots(data.slots);
  };

  const move = async (visit, slot) => {
    setBusy(true);
    try {
      await api.post(`/encounters/${visit.encounter_id}/reschedule`, { slot_start: slot.start });
      toast.success(`Moved to ${slot.label}`);
      setRescheduling(null);
      load();
    } catch (e) {
      toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Could not move it");
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (visit) => {
    if (!window.confirm("Cancel this visit? The time goes back to the clinic's open slots.")) return;
    try {
      await api.post(`/encounters/${visit.encounter_id}/cancel`);
      toast.success("Visit cancelled");
      load();
    } catch {
      toast.error("Could not cancel that visit");
    }
  };

  if (!visits || visits.length === 0) return null;

  return (
    <div className="card p-5" data-testid="upcoming-visits">
      <h2 className="text-sm font-semibold flex items-center gap-2 mb-3">
        <CalendarClock className="h-4 w-4 text-forest" /> Your upcoming visits
      </h2>
      <div className="space-y-3">
        {visits.map((visit) => (
          <div key={visit.encounter_id} className="border border-line rounded-xl px-4 py-3"
            data-testid={`visit-${visit.encounter_id}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium">
                  {visit.slot_label || new Date(visit.scheduled_at).toLocaleString()}
                </p>
                <p className="text-xs text-ink-soft mt-0.5">
                  {visit.doctor?.name}
                  {visit.doctor?.specialty ? ` · ${visit.doctor.specialty}` : ""}
                  {visit.reason_for_visit ? ` · ${visit.reason_for_visit}` : ""}
                </p>
                {visit.doctor?.clinic_phone && (
                  <a href={`tel:${visit.doctor.clinic_phone}`}
                    className="text-xs text-forest mt-1 inline-flex items-center gap-1">
                    <PhoneCall className="h-3 w-3" /> {visit.doctor.clinic_phone}
                  </a>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => (rescheduling === visit.encounter_id ? setRescheduling(null)
                  : openReschedule(visit))}
                  data-testid={`reschedule-btn-${visit.encounter_id}`} className="btn-outline !py-1.5 !px-3 text-xs">
                  <RefreshCw className="h-3.5 w-3.5" /> Reschedule
                </button>
                <button onClick={() => cancel(visit)} data-testid={`cancel-visit-btn-${visit.encounter_id}`}
                  className="btn-outline !py-1.5 !px-3 text-xs !border-terracotta !text-terracotta">
                  <CalendarX className="h-3.5 w-3.5" /> Cancel
                </button>
              </div>
            </div>

            {rescheduling === visit.encounter_id && (
              <div className="mt-3 border-t border-line pt-3" data-testid={`reschedule-slots-${visit.encounter_id}`}>
                <p className="text-xs text-ink-soft mb-2">Pick a new time with {visit.doctor?.name}:</p>
                <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
                  {slots.length === 0 && <p className="text-xs text-ink-soft">No other times available.</p>}
                  {slots.slice(0, 40).map((slot) => (
                    <button key={slot.start} onClick={() => move(visit, slot)} disabled={busy}
                      data-testid={`reschedule-slot-${slot.start}`}
                      className="px-2.5 py-1.5 rounded-full border border-line text-[11px] font-semibold hover:bg-forest hover:text-white hover:border-forest transition-colors">
                      {slot.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { toast } from "sonner";
import { CalendarDays, PhoneCall, Stethoscope, Search, CheckCircle2 } from "lucide-react";
import { UpcomingVisits } from "../components/UpcomingVisits";

export default function BookVisit() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [doctors, setDoctors] = useState(null);
  const [specialty, setSpecialty] = useState(params.get("specialty") || "");
  const [city, setCity] = useState("");
  const [selected, setSelected] = useState(null);
  const [slots, setSlots] = useState([]);
  const [reason, setReason] = useState(params.get("reason") || "");
  const [booking, setBooking] = useState(false);
  const [visitsKey, setVisitsKey] = useState(0);
  const reportId = params.get("report");

  const loadDoctors = (s, c) => {
    setDoctors(null);
    api.get("/booking/doctors", { params: { specialty: s || undefined, city: c || undefined } })
      .then(({ data }) => setDoctors(data)).catch(() => setDoctors([]));
  };

  useEffect(() => { loadDoctors(specialty, city); /* eslint-disable-next-line */ }, []);

  const pick = async (doctor) => {
    setSelected(doctor);
    setSlots([]);
    const { data } = await api.get("/booking/slots", { params: { doctor_user_id: doctor.user_id, days: 14 } });
    setSlots(data.slots);
    if (data.slots.length === 0) toast.info(`${doctor.name} has no open slots in the next two weeks`);
  };

  const book = async (slot) => {
    setBooking(true);
    try {
      const { data } = await api.post("/booking", {
        doctor_user_id: selected.user_id, slot_start: slot.start,
        reason_for_visit: reason, report_id: reportId || null,
      });
      toast.success(`Booked with ${data.doctor_name} — ${data.slot_label}`);
      setVisitsKey((k) => k + 1);
      navigate("/dashboard");
    } catch (e) {
      toast.error(typeof e?.response?.data?.detail === "string"
        ? e.response.data.detail : "Could not book that time");
      if (selected) pick(selected);
    } finally {
      setBooking(false);
    }
  };

  const byDate = slots.reduce((acc, s) => {
    (acc[s.date] = acc[s.date] || []).push(s);
    return acc;
  }, {});

  return (
    <div className="space-y-6 fade-up max-w-4xl" data-testid="book-visit-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Book a visit</h1>
        <p className="text-ink-soft mt-1">
          Your own doctor comes first. If your screening points at another specialty, you can pick a clinician who
          covers it — booking with them lets them read your record for this visit.
        </p>
      </div>

      <UpcomingVisits reloadKey={visitsKey} />

      <div className="card p-5 space-y-3">
        <label className="text-sm block">
          <span className="text-xs uppercase tracking-[0.15em] text-ink-soft">What is the visit about?</span>
          <input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="booking-reason-input"
            placeholder="e.g. Persistent headache and high blood pressure readings"
            className="mt-1 w-full border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
        </label>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} data-testid="booking-specialty-input"
            placeholder="Specialty (e.g. Cardiology)"
            className="border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
          <input value={city} onChange={(e) => setCity(e.target.value)} data-testid="booking-city-input"
            placeholder="City (e.g. Riyadh)"
            className="border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
          <button onClick={() => loadDoctors(specialty, city)} className="btn-outline" data-testid="booking-search-btn">
            <Search className="h-4 w-4" /> Find clinicians
          </button>
        </div>
      </div>

      {doctors === null && <div className="card p-6 text-sm text-ink-soft">Finding clinicians…</div>}
      {doctors?.length === 0 && (
        <div className="card p-8 text-center" data-testid="no-doctors">
          <Stethoscope className="h-7 w-7 text-forest mx-auto" />
          <p className="mt-3 font-semibold">No clinician matches that search</p>
          <p className="text-sm text-ink-soft mt-1">Try a different specialty or city, or clear the filters.</p>
        </div>
      )}

      <div className="space-y-4">
        {(doctors || []).map((doctor) => (
          <div key={doctor.user_id} className="card p-5" data-testid={`doctor-${doctor.user_id}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold flex items-center gap-2">
                  {doctor.name}
                  {doctor.is_my_doctor && (
                    <span className="text-[10px] uppercase tracking-wider bg-forest/10 text-forest px-1.5 py-0.5 rounded-full"
                      data-testid="my-doctor-badge">Your doctor</span>
                  )}
                </p>
                <p className="text-xs text-ink-soft mt-0.5">
                  {[doctor.specialty, doctor.clinic, doctor.city].filter(Boolean).join(" · ") || "No profile yet"}
                </p>
                {doctor.clinic_phone && (
                  <a href={`tel:${doctor.clinic_phone}`} data-testid={`clinic-phone-${doctor.user_id}`}
                    className="text-xs text-forest mt-1 inline-flex items-center gap-1">
                    <PhoneCall className="h-3 w-3" /> {doctor.clinic_phone}
                  </a>
                )}
              </div>
              <button onClick={() => pick(doctor)} data-testid={`show-slots-${doctor.user_id}`}
                className="btn-outline !py-1.5 !px-3 text-xs">
                <CalendarDays className="h-3.5 w-3.5" /> {doctor.publishes_slots ? "See times" : "No times published"}
              </button>
            </div>

            {selected?.user_id === doctor.user_id && (
              <div className="mt-4 space-y-3" data-testid={`slots-${doctor.user_id}`}>
                {Object.keys(byDate).length === 0 && (
                  <p className="text-sm text-ink-soft">No open times in the next two weeks.</p>
                )}
                {Object.entries(byDate).map(([date, daySlots]) => (
                  <div key={date}>
                    <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-1.5">
                      {new Date(date).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {daySlots.map((slot) => (
                        <button key={slot.start} onClick={() => book(slot)} disabled={booking}
                          data-testid={`slot-${slot.start}`}
                          className="px-3 py-1.5 rounded-full border border-line text-xs font-semibold hover:bg-forest hover:text-white hover:border-forest transition-colors">
                          {slot.local_time}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                <p className="text-xs text-ink-soft flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-forest" /> Picking a time confirms the visit straight away.
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

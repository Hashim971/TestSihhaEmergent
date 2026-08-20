import React, { useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Clock, Plus, Trash2, CalendarCheck } from "lucide-react";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export function AvailabilityCard() {
  const [state, setState] = useState(null);
  const [saving, setSaving] = useState(false);

  React.useEffect(() => {
    api.get("/doctor/availability").then(({ data }) => setState({
      slot_minutes: data.slot_minutes || 30,
      tz_offset_minutes: data.tz_offset_minutes ?? 180,
      weekly: data.weekly || [],
      blocked_dates: data.blocked_dates || [],
    })).catch(() => setState({ slot_minutes: 30, tz_offset_minutes: 180, weekly: [], blocked_dates: [] }));
  }, []);

  if (!state) return null;

  const addBlock = () => setState({ ...state, weekly: [...state.weekly, { weekday: 0, start: "09:00", end: "13:00" }] });
  const setBlock = (i, patch) => setState({
    ...state, weekly: state.weekly.map((b, idx) => (idx === i ? { ...b, ...patch } : b)),
  });
  const removeBlock = (i) => setState({ ...state, weekly: state.weekly.filter((_, idx) => idx !== i) });

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/doctor/availability", state);
      toast.success("Your clinic hours are published — patients can book these times.");
    } catch (e) {
      toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail
        : "Could not save your hours");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card p-8" data-testid="availability-card">
      <h2 className="text-xl font-semibold mb-2 flex items-center gap-2">
        <CalendarCheck className="h-5 w-5 text-forest" /> Clinic Hours
      </h2>
      <p className="text-sm text-ink-soft mb-6">
        Patients book directly into these times, in your local time. A booked slot disappears for everyone else.
      </p>

      <div className="flex flex-wrap items-center gap-4 mb-5">
        <label className="text-sm">
          <span className="text-xs uppercase tracking-[0.15em] text-ink-soft block">Appointment length</span>
          <select value={state.slot_minutes} data-testid="slot-minutes-select"
            onChange={(e) => setState({ ...state, slot_minutes: parseInt(e.target.value, 10) })}
            className="mt-1 border border-line rounded-lg px-3 py-2 text-sm bg-white">
            {[15, 20, 30, 45, 60].map((m) => <option key={m} value={m}>{m} minutes</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="text-xs uppercase tracking-[0.15em] text-ink-soft block">Your time zone</span>
          <select value={state.tz_offset_minutes} data-testid="tz-select"
            onChange={(e) => setState({ ...state, tz_offset_minutes: parseInt(e.target.value, 10) })}
            className="mt-1 border border-line rounded-lg px-3 py-2 text-sm bg-white">
            <option value={180}>Riyadh (UTC+3)</option>
            <option value={240}>Dubai (UTC+4)</option>
            <option value={120}>Cairo (UTC+2)</option>
            <option value={0}>UTC</option>
          </select>
        </label>
      </div>

      <div className="space-y-2">
        {state.weekly.map((block, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2" data-testid={`availability-block-${i}`}>
            <select value={block.weekday} data-testid={`block-weekday-${i}`}
              onChange={(e) => setBlock(i, { weekday: parseInt(e.target.value, 10) })}
              className="border border-line rounded-lg px-3 py-2 text-sm bg-white">
              {DAYS.map((d, idx) => <option key={d} value={idx}>{d}</option>)}
            </select>
            <input type="time" value={block.start} data-testid={`block-start-${i}`}
              onChange={(e) => setBlock(i, { start: e.target.value })}
              className="border border-line rounded-lg px-3 py-2 text-sm" />
            <span className="text-ink-soft text-sm">to</span>
            <input type="time" value={block.end} data-testid={`block-end-${i}`}
              onChange={(e) => setBlock(i, { end: e.target.value })}
              className="border border-line rounded-lg px-3 py-2 text-sm" />
            <button onClick={() => removeBlock(i)} data-testid={`remove-block-${i}`}
              className="p-2 rounded-full text-terracotta hover:bg-terracotta/10">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {state.weekly.length === 0 && (
          <p className="text-sm text-ink-soft" data-testid="no-hours">
            No hours published yet — patients cannot book with you until you add some.
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-5">
        <button onClick={addBlock} className="btn-outline" data-testid="add-availability-block-btn">
          <Plus className="h-4 w-4" /> Add hours
        </button>
        <button onClick={save} disabled={saving} className="btn-primary" data-testid="save-availability-btn">
          <Clock className="h-4 w-4" /> {saving ? "Saving…" : "Publish Hours"}
        </button>
      </div>
    </div>
  );
}

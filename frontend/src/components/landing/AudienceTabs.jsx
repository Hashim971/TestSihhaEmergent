import React, { useState } from "react";
import { HeartPulse, Stethoscope, Building2, Check } from "lucide-react";

const AUDIENCES = {
  patients: {
    icon: HeartPulse, label: "Patients",
    headline: "A health companion that knows when to call the doctor.",
    points: ["AI health chat and screening with a clear next step", "Book a published slot instantly — assigned doctor first", "Medications, reminders, refills and pill ID", "Visit summaries and prescriptions in Arabic or English", "Family profiles for children and parents"],
  },
  clinicians: {
    icon: Stethoscope, label: "Clinicians",
    headline: "Less typing, better visits.",
    points: ["Pre-visit briefing from screening, vitals and adherence", "Live Arabic transcript and AI-drafted SOAP notes", "Itemised prescriptions sent to the patient or a partner pharmacy", "Doctor-reviewed patient summaries with red-flag warnings", "Schedule, availability and urgent-case alerts"],
  },
  hospitals: {
    icon: Building2, label: "Hospitals",
    headline: "Your digital front door, ready in days.",
    points: ["White-label app under your name, colours and address", "Choose modules per hospital with feature switches", "Import existing patients and history by CSV", "Overview of every customer and staff member", "Separate staging workspace to test before go-live"],
  },
};

export function AudienceTabs() {
  const [tab, setTab] = useState("patients");
  const a = AUDIENCES[tab];
  return (
    <div className="mt-10 grid grid-cols-1 lg:grid-cols-12 gap-8" data-testid="audience-tabs">
      <div className="lg:col-span-4 flex lg:flex-col gap-2 overflow-x-auto pb-1 -mx-1 px-1 max-w-full">
        {Object.entries(AUDIENCES).map(([k, v]) => {
          const Icon = v.icon;
          return (
            <button key={k} onClick={() => setTab(k)} data-testid={`audience-tab-${k}`}
              className={`flex items-center gap-2 sm:gap-3 px-4 sm:px-5 py-3 sm:py-4 rounded-2xl text-left whitespace-nowrap border shrink-0 ${tab === k ? "bg-forest text-white border-forest" : "bg-white border-line hover:border-forest/30"}`}
              style={{ transition: "background-color 0.25s ease, border-color 0.25s ease" }}>
              <Icon className="h-5 w-5" /> <span className="font-semibold">{v.label}</span>
            </button>
          );
        })}
      </div>
      <div key={tab} className="lg:col-span-8 card p-8 sm:p-10 fade-up" data-testid={`audience-panel-${tab}`}>
        <h3 className="text-2xl font-semibold tracking-tight">{a.headline}</h3>
        <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {a.points.map((p) => (
            <li key={p} className="flex gap-3 text-sm text-ink-soft"><Check className="h-5 w-5 text-forest shrink-0" /> {p}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

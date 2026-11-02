import React from "react";
import { ChecklistItems } from "./OverviewTab";

const NEEDS = [
  ["Hospital details", "Legal name, commercial registration (CR) number, city, and a main contact person."],
  ["Brand kit", "Logo (SVG or high-resolution PNG), main and accent colour codes, and the name patients should see."],
  ["Web address", "A subdomain such as care.hospital.sa and someone in IT who can add one DNS record."],
  ["Staff list", "Name, work email and role (doctor or hospital admin) for each person who needs access."],
  ["Patient data (optional)", "An export of existing patients: name, email, phone, date of birth, conditions, allergies, medicines and last visit."],
  ["Feature choices", "Which modules to switch on: AI chat, pill ID, booking, prescriptions, visit summaries, pharmacy, live transcript."],
  ["Language", "Arabic or English as the default for patient-facing text."],
  ["Data agreement", "A signed data processing agreement covering Saudi PDPL before real patient data is imported."],
];

export function OnboardingTab({ overview }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="account-onboarding-tab">
      <div className="card p-6">
        <h3 className="font-semibold mb-1">Setup progress</h3>
        <p className="text-sm text-ink-soft mb-4">{overview.checklist_done} of {overview.checklist.length} steps done</p>
        <ChecklistItems items={overview.checklist} />
      </div>
      <div className="card p-6" data-testid="onboarding-requirements">
        <h3 className="font-semibold mb-1">What a hospital needs to plug in</h3>
        <p className="text-sm text-ink-soft mb-4">Send this list to the hospital before the kickoff call.</p>
        <ol className="space-y-3">
          {NEEDS.map(([title, desc], i) => (
            <li key={title} className="flex gap-3">
              <span className="h-6 w-6 rounded-full bg-forest text-white text-xs font-bold flex items-center justify-center shrink-0">{i + 1}</span>
              <span><span className="block text-sm font-medium">{title}</span><span className="block text-xs text-ink-soft">{desc}</span></span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

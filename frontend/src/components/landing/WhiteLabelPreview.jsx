import React, { useState } from "react";
import { Leaf, CalendarPlus, MessageSquare } from "lucide-react";

const BRANDS = [
  { name: "Sihha AI", primary: "#1E3F2A", accent: "#B1D8B7", domain: "app.sihha.ai" },
  { name: "Al Noor Care", primary: "#0F4C5C", accent: "#E3B23C", domain: "care.alnoor.sa" },
  { name: "Eastern Health", primary: "#5B2A86", accent: "#F2C6DE", domain: "my.easternhealth.sa" },
  { name: "Jeddah Family", primary: "#B4432B", accent: "#F6D6C2", domain: "app.jfc.sa" },
];

export function WhiteLabelPreview() {
  const [b, setB] = useState(BRANDS[1]);
  return (
    <div className="rounded-3xl bg-sand border border-line p-6 sm:p-8" data-testid="white-label-preview">
      <div className="flex flex-wrap gap-2 mb-6">
        {BRANDS.map((x) => (
          <button key={x.name} onClick={() => setB(x)} data-testid={`white-label-swatch-${x.name.replace(/\s+/g, "-").toLowerCase()}`}
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium bg-white ${b.name === x.name ? "border-ink" : "border-line"}`}>
            <span className="h-3.5 w-3.5 rounded-full" style={{ background: x.primary }} /> {x.name}
          </button>
        ))}
      </div>
      <div className="rounded-2xl bg-white border border-line shadow-xl overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-line bg-sand/60">
          <span className="h-2.5 w-2.5 rounded-full bg-red-300" /><span className="h-2.5 w-2.5 rounded-full bg-amber-300" /><span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
          <span className="ml-3 text-[11px] font-mono text-ink-soft bg-white border border-line rounded px-2 py-0.5" data-testid="white-label-domain">https://{b.domain}</span>
        </div>
        <div className="grid grid-cols-12 min-h-[300px]">
          <div className="col-span-4 border-r border-line p-4 space-y-2 hidden sm:block">
            <div className="flex items-center gap-2 mb-4">
              <span className="h-8 w-8 rounded-full flex items-center justify-center" style={{ background: b.primary, transition: "background-color 0.3s ease" }}><Leaf className="h-4 w-4" style={{ color: b.accent }} /></span>
              <span className="font-heading font-bold text-sm" style={{ color: b.primary }}>{b.name}</span>
            </div>
            {["Dashboard", "Health Chat", "Book a Visit", "Prescriptions"].map((n, i) => (
              <div key={n} className="rounded-lg px-3 py-2 text-xs font-medium" style={i === 0 ? { background: b.primary, color: "#fff" } : { color: "#525252" }}>{n}</div>
            ))}
          </div>
          <div className="col-span-12 sm:col-span-8 p-5 space-y-4">
            <p className="font-semibold">مرحباً، عمر · Good morning, Omar</p>
            <div className="rounded-xl p-4 text-white text-sm" style={{ background: b.primary, transition: "background-color 0.3s ease" }}>
              Your visit with Dr. Layla is tomorrow at 10:00
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl p-4 text-sm font-medium flex items-center gap-2" style={{ background: b.accent, color: b.primary }}><CalendarPlus className="h-4 w-4" /> Book a visit</div>
              <div className="rounded-xl p-4 text-sm font-medium border border-line flex items-center gap-2"><MessageSquare className="h-4 w-4" style={{ color: b.primary }} /> Health chat</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

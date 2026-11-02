import React from "react";
import { ArrowRight, Palette, Globe, ToggleRight, ShieldCheck } from "lucide-react";

const POINTS = [
  [Palette, "Your logo, colours and name", "Patients only ever see your hospital's brand."],
  [Globe, "Your own web address", "care.yourhospital.sa, plus a branded sign-in page."],
  [ToggleRight, "Only the modules you want", "Screening, booking, scribe, pharmacy — switch each on or off."],
  [ShieldCheck, "Built for Saudi healthcare", "Arabic and English, right-to-left, with your data kept per hospital."],
];

export function WhiteLabelCallout() {
  return (
    <section className="max-w-7xl mx-auto px-6 py-20" data-testid="white-label-callout">
      <div className="rounded-3xl bg-forest text-white p-8 sm:p-12 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center relative overflow-hidden">
        <div className="absolute -end-20 -top-20 h-64 w-64 rounded-full bg-sage/20" />
        <div className="lg:col-span-5 relative">
          <p className="text-xs uppercase tracking-[0.2em] text-sage font-semibold">For hospitals and clinic groups</p>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-3">Sihha AI is available as a white-label solution</h2>
          <p className="text-white/80 mt-4 leading-relaxed">Launch your own AI health app in weeks, not years. We run the platform; your patients see your hospital.</p>
          <a href="#demo" className="mt-8 inline-flex items-center gap-2 rounded-full bg-white text-forest font-semibold px-6 py-3 hover:bg-sage" style={{ transition: "background-color 0.2s ease" }} data-testid="white-label-talk-btn">
            Talk to us <ArrowRight className="h-4 w-4 rtl:rotate-180" />
          </a>
        </div>
        <ul className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4 relative">
          {POINTS.map(([Icon, title, desc]) => (
            <li key={title} className="rounded-2xl bg-white/10 border border-white/15 p-5 backdrop-blur-md">
              <Icon className="h-5 w-5 text-sage" />
              <p className="font-semibold mt-3">{title}</p>
              <p className="text-sm text-white/75 mt-1">{desc}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

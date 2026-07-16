import React from "react";

export default function YesNo({ label, desc, value, onChange, details, onDetails, placeholder, testid }) {
  return (
    <div>
      <p className="font-semibold">{label}</p>
      {desc && <p className="text-sm text-ink-soft mt-1 leading-relaxed">{desc}</p>}
      <div className="flex gap-3 mt-3">
        {[["Yes", true], ["No", false]].map(([txt, val]) => (
          <button key={txt} type="button" onClick={() => onChange(val)}
            data-testid={`${testid}-${txt.toLowerCase()}`}
            className={`px-8 py-2 rounded-full text-sm font-medium border ${
              value === val ? "bg-forest text-white border-forest" : "bg-sand text-ink-soft border-line hover:bg-white"
            }`}
            style={{ transition: "background-color 0.2s ease, color 0.2s ease" }}>
            {txt}
          </button>
        ))}
      </div>
      {value === true && onDetails && (
        <textarea value={details} onChange={(e) => onDetails(e.target.value)} placeholder={placeholder}
          data-testid={`${testid}-details`} rows={2}
          className="mt-3 w-full border border-line rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
      )}
    </div>
  );
}

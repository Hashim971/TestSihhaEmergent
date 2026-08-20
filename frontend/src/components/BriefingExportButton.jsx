import React, { useState } from "react";
import jsPDF from "jspdf";
import { FileDown } from "lucide-react";

const line = (doc, text, y, indent = 15, size = 10) => {
  doc.setFontSize(size);
  const wrapped = doc.splitTextToSize(text, 195 - indent);
  doc.text(wrapped, indent, y);
  return y + wrapped.length * (size * 0.55) + 2;
};

export function BriefingExportButton({ artifact, content, patientName, encounter }) {
  const [busy, setBusy] = useState(false);

  const download = () => {
    setBusy(true);
    try {
      const doc = new jsPDF();
      let y = 20;
      doc.setFontSize(16);
      doc.text("Pre-visit briefing", 15, y);
      y += 8;
      doc.setFontSize(9);
      y = line(doc, `${patientName || "Patient"} · ${encounter?.reason_for_visit || "No reason recorded"}`, y, 15, 9);
      y = line(doc, `Visit ${encounter?.slot_label || new Date(encounter?.scheduled_at).toLocaleString()}`
        + `  ·  ${artifact.status === "signed" ? `Signed ${new Date(artifact.signed_at).toLocaleString()}`
          : "Unsigned draft"}`, y, 15, 9);
      y += 4;

      y = line(doc, content.headline || "", y, 15, 12);
      y += 2;

      const section = (title, rows) => {
        if (!rows?.length) return;
        doc.setFontSize(11);
        doc.setFont(undefined, "bold");
        if (y > 265) { doc.addPage(); y = 20; }
        doc.text(title, 15, y);
        doc.setFont(undefined, "normal");
        y += 6;
        rows.forEach((row) => {
          if (y > 275) { doc.addPage(); y = 20; }
          y = line(doc, `• ${row}`, y, 18, 10);
        });
        y += 3;
      };

      section("Chief concerns", (content.chief_concerns || []).map((c) =>
        `${c.concern} [${c.priority}] — ${c.evidence}`));
      section("Vitals", (content.vitals_summary || []).map((v) =>
        `${v.metric}: ${v.current} (${v.trend})${v.note ? ` — ${v.note}` : ""}`));
      section("Medication review", (content.medication_review || []).map((m) =>
        `${m.medication}${m.adherence_pct != null ? ` — ${m.adherence_pct}% adherence` : ""}`
        + `${m.flag && m.flag !== "none" ? ` [${m.flag}]` : ""}${m.note ? ` — ${m.note}` : ""}`));
      section("Discussion points", content.suggested_discussion_points);
      section("Data gaps", content.data_gaps);

      doc.setFontSize(8);
      doc.text("AI-generated briefing reviewed by the treating clinician. Not a diagnosis.", 105, 288,
        { align: "center" });
      doc.save(`sihha-briefing-${(patientName || "patient").replace(/\s+/g, "-").toLowerCase()}.pdf`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button onClick={download} disabled={busy} className="btn-outline !py-1.5 !px-3 text-xs"
      data-testid="export-briefing-btn">
      <FileDown className="h-3.5 w-3.5" /> {busy ? "Preparing…" : "Download PDF"}
    </button>
  );
}

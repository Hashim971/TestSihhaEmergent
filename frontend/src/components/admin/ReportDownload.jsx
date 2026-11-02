import React, { useState } from "react";
import { FileDown } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";

const lastMonth = () => {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};

export function ReportDownload({ endpoint, initialMonth, testid = "report-download" }) {
  const [month, setMonth] = useState(initialMonth || lastMonth());
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      const res = await api.get(endpoint, { params: { month }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      Object.assign(document.createElement("a"), { href: url, download: `usage-report-${month}.pdf` }).click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Could not create the report");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex items-center gap-2" data-testid={testid}>
      <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} data-testid={`${testid}-month`} className="border border-line rounded-md px-2 py-1.5 text-sm bg-white" />
      <button onClick={download} disabled={busy || !month} data-testid={`${testid}-btn`} className="btn-outline">
        <FileDown className="h-4 w-4" /> {busy ? "Preparing…" : "Usage report (PDF)"}
      </button>
    </div>
  );
}

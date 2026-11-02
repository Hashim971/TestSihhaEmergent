import React, { useState } from "react";
import { FileSpreadsheet, Download, Upload } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { errorText } from "./ui";

const TEMPLATE = [
  "name,email,phone,date_of_birth,gender,conditions,allergies,medications,last_visit,notes",
  "Sara Al Qahtani,sara@example.com,+966500000001,1988-04-12,female,Type 2 diabetes;Hypertension,Penicillin,Metformin 500mg;Amlodipine 5mg,2026-05-20,Annual review due",
].join("\n");

export function ImportTab({ account, onDone }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const downloadTemplate = () => {
    const url = URL.createObjectURL(new Blob([TEMPLATE], { type: "text/csv" }));
    Object.assign(document.createElement("a"), { href: url, download: "sihha-patient-import-template.csv" }).click();
    URL.revokeObjectURL(url);
  };

  const run = async () => {
    const body = new FormData();
    body.append("file", file);
    setBusy(true);
    try {
      const { data } = await api.post(`/admin/accounts/${account.account_id}/import`, body);
      setResult(data);
      toast.success(`Imported ${data.created + data.linked} patients`);
      onDone();
    } catch (e) {
      toast.error(errorText(e, "Import failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="account-import-tab">
      <div className="card p-6 space-y-4">
        <h3 className="font-semibold">Bring in existing patients and their history</h3>
        <p className="text-sm text-ink-soft">
          Upload a CSV with one patient per row. <b>name</b> and <b>email</b> are required. Separate multiple conditions, allergies or medicines with <code>;</code>.
          Imported patients are added as customers of this hospital and can set a password later through “Forgot password”.
        </p>
        <button onClick={downloadTemplate} data-testid="import-template-btn" className="btn-outline"><Download className="h-4 w-4" /> Download template</button>
        <label className="flex items-center gap-3 border border-dashed border-line rounded-lg p-5 cursor-pointer hover:bg-sand" data-testid="import-dropzone">
          <FileSpreadsheet className="h-6 w-6 text-forest" />
          <span className="text-sm text-ink-soft truncate">{file ? file.name : "Choose a .csv file (UTF-8, up to 2 MB / 2,000 rows)"}</span>
          <input type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); }} data-testid="import-file-input" />
        </label>
        <button onClick={run} disabled={!file || busy} data-testid="import-run-btn" className="btn-primary"><Upload className="h-4 w-4" /> {busy ? "Importing…" : "Import patients"}</button>
      </div>
      <div className="card p-6" data-testid="import-result">
        <h3 className="font-semibold mb-3">Result</h3>
        {!result && <p className="text-sm text-ink-soft">The import summary appears here.</p>}
        {result && (
          <>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <Stat label="New" value={result.created} testid="import-created" />
              <Stat label="Linked" value={result.linked} testid="import-linked" />
              <Stat label="Skipped" value={result.error_count} testid="import-errors" />
            </div>
            {result.errors.length > 0 && (
              <ul className="text-xs text-terracotta space-y-1 max-h-48 overflow-y-auto">
                {result.errors.map((e, i) => <li key={i}>Row {e.row}: {e.reason}</li>)}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const Stat = ({ label, value, testid }) => (
  <div className="rounded-lg bg-sand p-3 text-center" data-testid={testid}>
    <p className="text-2xl font-bold">{value}</p>
    <p className="text-[11px] uppercase tracking-wider text-ink-soft">{label}</p>
  </div>
);

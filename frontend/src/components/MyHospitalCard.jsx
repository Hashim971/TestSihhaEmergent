import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Building2, LogOut, Search } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export function MyHospitalCard() {
  const { user, setUser } = useAuth();
  const [link, setLink] = useState(null);

  useEffect(() => { api.get("/profile/hospital").then(({ data }) => setLink(data)).catch(() => setLink({ hospital: null })); }, []);

  const leave = async () => {
    if (!window.confirm("Leave this hospital? Its doctors will no longer see your record.")) return;
    try {
      const { data } = await api.put("/profile/hospital", { account_id: null });
      setLink(data);
      setUser({ ...user, account_id: null });
      toast.success("You're now using Sihha on your own");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not leave the hospital");
    }
  };

  if (!link) return null;
  const h = link.hospital;
  return (
    <div className="card p-6" data-testid="my-hospital-card">
      <h2 className="text-lg font-semibold flex items-center gap-2"><Building2 className="h-4 w-4 text-forest" /> My hospital</h2>
      {h ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold" data-testid="my-hospital-name">{h.name}</p>
            <p className="text-xs text-ink-soft">{[h.city, link.doctor && `Your doctor: ${link.doctor.name}`].filter(Boolean).join(" · ")}</p>
          </div>
          <div className="flex gap-2">
            <Link to="/find-care" className="btn-outline !py-1.5 !px-3 text-xs" data-testid="change-hospital-btn"><Search className="h-3.5 w-3.5" /> Change hospital</Link>
            <button onClick={leave} className="btn-outline !py-1.5 !px-3 text-xs !text-terracotta !border-terracotta" data-testid="leave-hospital-btn"><LogOut className="h-3.5 w-3.5" /> Leave</button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3" data-testid="standalone-mode">
          <p className="text-sm text-ink-soft max-w-md">You're using Sihha on your own. Medications, screenings and reminders all work without a hospital — link one when you want to book a doctor.</p>
          <Link to="/find-care" className="btn-primary !py-2 text-sm" data-testid="find-hospital-btn"><Search className="h-4 w-4" /> Find a hospital</Link>
        </div>
      )}
      <p className="text-xs text-ink-soft mt-3">You can be linked to one hospital at a time. Switching removes the previous hospital's access to your record.</p>
    </div>
  );
}

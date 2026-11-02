import React, { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { ReportDownload } from "../components/admin/ReportDownload";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { OverviewTab } from "../components/admin/OverviewTab";
import { PeopleTab } from "../components/admin/PeopleTab";
import { IdChip } from "../components/admin/ui";
import { ListingTab } from "../components/admin/ListingTab";

const TABS = [["overview", "Overview"], ["staff", "Staff"], ["customers", "Customers"], ["listing", "App listing"]];

export default function MyHospital() {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [tab, setTab] = useState("overview");
  const [params] = useSearchParams();

  useEffect(() => { api.get("/account/overview").then(({ data }) => setOverview(data)).catch(() => {}); }, []);

  if (user.account_role !== "account_admin") return <Navigate to="/dashboard" replace />;
  if (!overview) return <p className="text-sm text-ink-soft">Loading…</p>;

  return (
    <div className="fade-up max-w-6xl" data-testid="my-hospital-page">
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{overview.account.name}</h1>
        <IdChip id={overview.account.account_id} testid="my-hospital-id" />
        <div className="ml-auto"><ReportDownload endpoint="/account/report" initialMonth={params.get("report")} testid="my-hospital-report" /></div>
      </div>
      <div className="flex gap-1 border-b border-line mb-6">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`my-hospital-tab-${k}`}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px ${tab === k ? "border-forest text-forest" : "border-transparent text-ink-soft"}`}>{label}</button>
        ))}
      </div>
      {tab === "overview" && <OverviewTab overview={overview} />}
      {tab === "listing" && <ListingTab account={overview.account} save={(patch) => api.patch("/account/listing", patch)} />}
      {(tab === "staff" || tab === "customers") && <PeopleTab key={tab} accountId={overview.account.account_id} kind={tab} readOnly base="/account/users" />}
    </div>
  );
}

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ChevronLeft, FlaskConical } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { usePlatform } from "../../context/PlatformContext";
import { rememberAccount } from "../../lib/recentAccounts";
import { StatusBadge, TypeBadge, IdChip, errorText } from "../../components/admin/ui";
import { OverviewTab } from "../../components/admin/OverviewTab";
import { PeopleTab } from "../../components/admin/PeopleTab";
import { BrandingTab } from "../../components/admin/BrandingTab";
import { FeaturesTab } from "../../components/admin/FeaturesTab";
import { DomainTab } from "../../components/admin/DomainTab";
import { ImportTab } from "../../components/admin/ImportTab";
import { OnboardingTab } from "../../components/admin/OnboardingTab";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "staff", label: "Staff" },
  { key: "customers", label: "Customers" },
  { key: "branding", label: "Branding", staging: true },
  { key: "features", label: "Features" },
  { key: "domain", label: "Domain & language", staging: true },
  { key: "import", label: "Import data", staging: true },
  { key: "onboarding", label: "Onboarding" },
];

export default function AccountWorkspace() {
  const { accountId } = useParams();
  const [params, setParams] = useSearchParams();
  const { env } = usePlatform();
  const [account, setAccount] = useState(null);
  const [overview, setOverview] = useState(null);
  const [error, setError] = useState(null);
  const tab = params.get("tab") || "overview";

  const currentId = useRef(accountId);
  currentId.current = accountId;

  const load = useCallback(async () => {
    try {
      const [a, o] = await Promise.all([api.get(`/admin/accounts/${accountId}`), api.get(`/admin/accounts/${accountId}/overview`)]);
      if (currentId.current !== accountId) return;
      setAccount(a.data);
      setOverview(o.data);
      rememberAccount(a.data);
    } catch (e) {
      if (currentId.current === accountId) setError(errorText(e, "Account not found"));
    }
  }, [accountId]);

  useEffect(() => {
    setAccount(null);
    setOverview(null);
    setError(null);
    load();
  }, [load]);

  const onSaved = (a) => { setAccount(a); api.get(`/admin/accounts/${accountId}/overview`).then(({ data }) => setOverview(data)); };

  const setStatus = async (status) => {
    try {
      onSaved((await api.patch(`/admin/accounts/${accountId}`, { status })).data);
      toast.success(`Status set to ${status}`);
    } catch (e) {
      toast.error(errorText(e));
    }
  };

  if (error) return <div className="card p-10 text-center" data-testid="account-not-found">{error} · <Link to="/admin/accounts" className="underline">Back to accounts</Link></div>;
  if (!account || !overview) return <p className="text-sm text-ink-soft" data-testid="account-loading">Loading account…</p>;

  const tabs = TABS.filter((t) => !t.staging || env.is_staging);

  return (
    <div className="fade-up" data-testid="account-workspace">
      <Link to="/admin/accounts" className="inline-flex items-center gap-1 text-sm text-ink-soft hover:text-ink mb-4" data-testid="account-back-link"><ChevronLeft className="h-4 w-4" /> Accounts</Link>
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight" data-testid="account-title">{account.name}</h1>
        <IdChip id={account.account_id} testid="account-workspace-id" large />
        <TypeBadge type={account.type} />
        <StatusBadge status={account.status} testid="account-workspace-status" />
        <select value={account.status} onChange={(e) => setStatus(e.target.value)} data-testid="account-status-select" className="ml-auto border border-line rounded-md px-3 py-2 text-sm bg-white">
          <option value="trial">Trial</option><option value="subscribed">Subscribed</option><option value="suspended">Suspended</option>
        </select>
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-line mb-6" role="tablist">
        {tabs.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setParams({ tab: t.key })} data-testid={`account-tab-${t.key}`}
            className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px flex items-center gap-1.5 ${tab === t.key ? "border-forest text-forest" : "border-transparent text-ink-soft hover:text-ink"}`}>
            {t.label}{t.staging && <FlaskConical className="h-3 w-3 text-amber-600" />}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab overview={overview} />}
      {(tab === "staff" || tab === "customers") && <PeopleTab key={tab} accountId={account.account_id} kind={tab} initialQuery={params.get("q") || ""} />}
      {tab === "branding" && env.is_staging && <BrandingTab account={account} onSaved={onSaved} />}
      {tab === "features" && <FeaturesTab account={account} onSaved={onSaved} isStaging={env.is_staging} />}
      {tab === "domain" && env.is_staging && <DomainTab account={account} onSaved={onSaved} />}
      {tab === "import" && env.is_staging && <ImportTab account={account} onDone={load} />}
      {tab === "onboarding" && <OnboardingTab overview={overview} />}
    </div>
  );
}

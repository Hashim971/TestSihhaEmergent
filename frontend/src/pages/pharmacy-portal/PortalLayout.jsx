import React, { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet } from "react-router-dom";
import { Store, Inbox, Megaphone, LogOut, Clock, XCircle } from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";
import { LanguageToggle } from "../../components/LanguageToggle";

export default function PortalLayout() {
  const { user, logout } = useAuth();
  const [me, setMe] = useState(null);

  useEffect(() => { if (user.role === "pharmacist") api.get("/pharmacy-portal/me").then(({ data }) => setMe(data)).catch(() => setMe({ status: "error" })); }, [user.role]);

  if (user.role !== "pharmacist") return <Navigate to={user.role === "doctor" ? "/doctor" : "/dashboard"} replace />;
  if (!me) return <div className="min-h-screen bg-sand flex items-center justify-center text-sm text-ink-soft">Loading…</div>;

  const tab = ({ isActive }) => `inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${isActive ? "bg-forest text-white" : "text-ink-soft hover:bg-sand"}`;
  return (
    <div className="min-h-screen bg-sand" data-testid="pharmacy-portal">
      <header className="sticky z-10 bg-white/90 backdrop-blur-md border-b border-line" style={{ top: "var(--env-bar, 0px)" }}>
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center gap-3">
          <span className="h-9 w-9 rounded-xl bg-forest flex items-center justify-center"><Store className="h-5 w-5 text-sage" /></span>
          <div className="min-w-0">
            <p className="font-heading font-bold text-forest leading-tight truncate" data-testid="portal-pharmacy-name">{me.pharmacy?.name_en || "Pharmacy portal"}</p>
            <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft">{user.name} · {me.pharmacy_role || "pending"}</p>
          </div>
          {me.status === "approved" && (
            <nav className="flex gap-1 order-last sm:order-none w-full sm:w-auto sm:ms-6">
              <NavLink to="/pharmacy-portal" end className={tab} data-testid="portal-nav-orders"><Inbox className="h-4 w-4" /> Orders</NavLink>
              <NavLink to="/pharmacy-portal/sponsorship" className={tab} data-testid="portal-nav-sponsorship"><Megaphone className="h-4 w-4" /> Sponsorship</NavLink>
            </nav>
          )}
          <div className="ms-auto flex items-center gap-2">
            <LanguageToggle testid="portal-language-toggle" />
            <button onClick={logout} className="p-2 rounded-full hover:bg-sand" data-testid="portal-logout-btn"><LogOut className="h-4 w-4 text-ink-soft" /></button>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {me.status === "approved" ? <Outlet context={me} /> : <PendingState me={me} />}
      </main>
    </div>
  );
}

function PendingState({ me }) {
  const rejected = me.status === "rejected";
  const Icon = rejected ? XCircle : Clock;
  return (
    <div className="card p-10 max-w-lg mx-auto text-center fade-up" data-testid={rejected ? "portal-application-rejected" : "portal-application-pending"}>
      <Icon className={`h-10 w-10 mx-auto mb-3 ${rejected ? "text-terracotta" : "text-forest"}`} />
      <h1 className="text-2xl font-bold tracking-tight">{rejected ? "Application not approved" : "Waiting for approval"}</h1>
      <p className="text-sm text-ink-soft mt-2">
        {rejected
          ? me.application?.reason || "Your application was not approved. Contact us if you think this is a mistake."
          : `We're checking ${me.application?.pharmacy_name || "your pharmacy"}'s licence. You'll get an email once orders can reach you.`}
      </p>
    </div>
  );
}

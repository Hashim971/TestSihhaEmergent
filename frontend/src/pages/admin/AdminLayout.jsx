import React, { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { Building2, ToggleRight, UserCheck, Search, ArrowLeft, LogOut, ShieldCheck, Inbox, Store, LayoutDashboard, FlaskConical } from "lucide-react";
import { LanguageToggle } from "../../components/LanguageToggle";
import { useAuth } from "../../context/AuthContext";
import { usePlatform } from "../../context/PlatformContext";
import { AccountSwitcher } from "../../components/admin/AccountSwitcher";
import { QuickNav } from "../../components/admin/QuickNav";

const nav = [
  { to: "/admin/overview", label: "Overview", icon: LayoutDashboard, testid: "admin-nav-overview" },
  { to: "/admin/accounts", label: "Accounts", icon: Building2, testid: "admin-nav-accounts" },
  { to: "/admin/flags", label: "Feature switches", icon: ToggleRight, testid: "admin-nav-flags" },
  { to: "/admin/demo-requests", label: "Demo requests", icon: Inbox, testid: "admin-nav-demo-requests" },
  { to: "/admin/assignments", label: "Doctor assignments", icon: UserCheck, testid: "admin-nav-assignments" },
  { to: "/admin/pharmacies", label: "Pharmacies", icon: Store, testid: "admin-nav-pharmacies" },
  { to: "/admin/staging", label: "Staging", icon: FlaskConical, testid: "admin-nav-staging" },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const { env } = usePlatform();
  const [quick, setQuick] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setQuick(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!user.is_admin) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen bg-sand flex">
      <aside className="w-64 shrink-0 border-r border-line bg-white flex-col fixed bottom-0 left-0 z-20 hidden md:flex" style={{ top: "var(--env-bar, 0px)" }}>
        <div className="px-5 py-5 flex items-center gap-2 border-b border-line">
          <span className="h-9 w-9 rounded-xl bg-forest flex items-center justify-center"><ShieldCheck className="h-5 w-5 text-sage" /></span>
          <div>
            <p className="font-heading font-bold text-forest leading-tight">Super Admin</p>
            <p className="text-[10px] uppercase tracking-[0.15em] text-ink-soft" data-testid="admin-env-label">{env.is_staging ? "Staging" : "Production"}</p>
          </div>
        </div>
        <div className="px-4 pt-4 space-y-2">
          <AccountSwitcher />
          <button onClick={() => setQuick(true)} data-testid="quick-nav-btn"
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-ink-soft hover:bg-sand">
            <Search className="h-4 w-4" /> Quick nav
            <kbd className="ml-auto text-[10px] font-mono border border-line rounded px-1.5">⌘K</kbd>
          </button>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1 border-t border-line mt-4">
          {nav.map(({ to, label, icon: Icon, testid }) => (
            <NavLink key={to} to={to} data-testid={testid}
              className={({ isActive }) => `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium ${isActive ? "bg-forest text-white" : "text-ink-soft hover:bg-sand"}`}>
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-line space-y-2">
          <LanguageToggle className="w-full justify-center" testid="admin-language-toggle" />
          <button onClick={() => navigate(user.role === "doctor" ? "/doctor" : "/dashboard")} data-testid="admin-back-to-app-btn" className="btn-outline w-full justify-center text-xs">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to app
          </button>
          <button onClick={logout} data-testid="admin-logout-btn" className="w-full flex items-center justify-center gap-2 text-xs text-ink-soft py-1.5 hover:text-ink">
            <LogOut className="h-3.5 w-3.5" /> Sign out
          </button>
        </div>
      </aside>
      <div className="flex-1 md:ml-64 min-w-0">
        <header className="md:hidden sticky z-10 bg-white border-b border-line px-4 py-3 flex items-center gap-2" style={{ top: "var(--env-bar, 0px)" }}>
          <ShieldCheck className="h-5 w-5 text-forest" />
          <span className="font-semibold text-sm flex-1">Super Admin</span>
          <button onClick={() => setQuick(true)} data-testid="quick-nav-btn-mobile" className="p-2 rounded-full hover:bg-sand"><Search className="h-4 w-4" /></button>
          <NavLink to="/admin/accounts" className="text-xs font-medium text-forest" data-testid="admin-nav-accounts-mobile">Accounts</NavLink>
          <NavLink to="/admin/flags" className="text-xs font-medium text-forest" data-testid="admin-nav-flags-mobile">Switches</NavLink>
        </header>
        <main className="p-4 sm:p-6 lg:p-10 w-full max-w-[1600px]">
          <Outlet />
        </main>
      </div>
      <QuickNav open={quick} onClose={() => setQuick(false)} />
    </div>
  );
}

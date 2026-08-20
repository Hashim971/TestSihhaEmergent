import React, { useState, useEffect } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  LayoutDashboard, MessageSquare, ScanLine, Pill, Users,
  Stethoscope, Bell, LogOut, Leaf, ChevronDown, Share2, Settings as SettingsIcon, CalendarDays, UserCheck,
} from "lucide-react";

const patientNav = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/chat", label: "Health Chat", icon: MessageSquare, testid: "nav-chat" },
  { to: "/pill-id", label: "Pill ID", icon: ScanLine, testid: "nav-pill-id" },
  { to: "/medications", label: "Medications", icon: Pill, testid: "nav-medications" },
  { to: "/dependents", label: "Dependents", icon: Users, testid: "nav-dependents" },
  { to: "/settings", label: "Settings", icon: SettingsIcon, testid: "nav-settings" },
];

const doctorNav = [
  { to: "/doctor", label: "Dashboard", icon: LayoutDashboard, testid: "nav-doctor-dashboard" },
  { to: "/doctor/patients", label: "Patients", icon: Stethoscope, testid: "nav-doctor" },
  { to: "/doctor/schedule", label: "Schedule", icon: CalendarDays, testid: "nav-doctor-schedule" },
  { to: "/settings", label: "Settings", icon: SettingsIcon, testid: "nav-settings" },
];

export default function Layout() {
  const { user, setUser, logout, activeProfile, setActiveProfile, dependents } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [showAlerts, setShowAlerts] = useState(false);
  const [showProfiles, setShowProfiles] = useState(false);
  const navigate = useNavigate();

  const loadAlerts = async () => {
    try {
      const res = await api.get("/alerts");
      setAlerts(res.data);
    } catch {}
  };

  useEffect(() => { loadAlerts(); }, []);

  const unread = alerts.filter((a) => !a.read).length;

  const markRead = async (id) => {
    await api.post(`/alerts/${id}/read`);
    loadAlerts();
  };

  const toggleRole = async () => {
    const newRole = user.role === "doctor" ? "patient" : "doctor";
    try {
      const res = await api.post("/auth/role", { role: newRole });
      setUser(res.data);
      toast.success(`Switched to ${newRole} view`);
      navigate(newRole === "doctor" ? "/doctor" : "/dashboard");
    } catch (e) {
      if (e?.response?.status === 403) {
        toast.error("Role changes are managed by an administrator.");
      } else {
        toast.error(e?.response?.data?.detail || "Could not switch role");
      }
    }
  };

  const toggleSharing = async () => {
    const res = await api.post("/auth/sharing", { enabled: !user.sharing_enabled });
    setUser(res.data);
    toast.success(res.data.sharing_enabled ? "Now sharing data with doctors" : "Data sharing disabled");
  };

  return (
    <div className="min-h-screen bg-sand flex">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-line bg-white flex flex-col fixed inset-y-0 z-20 hidden md:flex">
        <div className="px-6 py-6 flex items-center gap-2 border-b border-line">
          <div className="h-9 w-9 rounded-full bg-forest flex items-center justify-center">
            <Leaf className="h-5 w-5 text-sage" />
          </div>
          <span className="font-heading font-bold text-xl text-forest">Sihha AI</span>
        </div>
        <nav className="flex-1 px-3 py-6 space-y-1">
          {(user.role === "doctor" ? doctorNav : patientNav).map(({ to, label, icon: Icon, testid }) => (
            <NavLink
              key={to} to={to} end={to === "/doctor"} data-testid={testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium ${
                  isActive ? "bg-forest text-white" : "text-ink-soft hover:bg-sand"
                }`
              }
            >
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
          {user.is_admin && (
            <NavLink
              to="/admin/assignments" data-testid="nav-admin-assignments"
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium ${
                  isActive ? "bg-forest text-white" : "text-ink-soft hover:bg-sand"
                }`
              }
            >
              <UserCheck className="h-4 w-4" /> Assignments
            </NavLink>
          )}
        </nav>
        <div className="p-4 border-t border-line space-y-2">
          {user.is_admin && (
            <button onClick={toggleRole} data-testid="toggle-role-btn" className="btn-outline w-full justify-center text-xs">
              <Stethoscope className="h-3.5 w-3.5" />
              {user.role === "doctor" ? "Switch to Patient" : "Switch to Doctor"}
            </button>
          )}
          {user.role !== "doctor" && (
            <button onClick={toggleSharing} data-testid="toggle-sharing-btn"
              className={`btn-outline w-full justify-center text-xs ${user.sharing_enabled ? "!bg-sage/30 !border-sage" : ""}`}>
              <Share2 className="h-3.5 w-3.5" />
              {user.sharing_enabled ? "Sharing: ON" : "Share with Doctors"}
            </button>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 md:ml-60 flex flex-col min-h-screen">
        <header className="sticky top-0 z-10 bg-white/90 backdrop-blur-md border-b border-line px-6 py-3 flex items-center justify-between">
          {/* Profile switcher — dependents are a patient concept */}
          {user.role === "doctor" ? (
            <p className="text-sm font-medium text-ink-soft" data-testid="doctor-context-label">
              Clinician workspace{user.is_admin ? " · Admin" : ""}
            </p>
          ) : (
          <div className="relative">
            <button
              onClick={() => setShowProfiles(!showProfiles)}
              data-testid="profile-switcher-btn"
              className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-line bg-white text-sm font-medium hover:bg-sand"
              style={{ transition: "background-color 0.2s ease" }}
            >
              <span className="h-6 w-6 rounded-full bg-sage text-forest flex items-center justify-center text-xs font-bold">
                {activeProfile.name.charAt(0).toUpperCase()}
              </span>
              {activeProfile.name}
              <ChevronDown className="h-3.5 w-3.5 text-ink-soft" />
            </button>
            {showProfiles && (
              <div className="absolute mt-2 w-56 bg-white border border-line rounded-xl shadow-md p-1.5 z-30">
                <button
                  data-testid="profile-option-self"
                  onClick={() => { setActiveProfile({ id: "self", name: "Me" }); setShowProfiles(false); }}
                  className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-sand"
                >
                  Me ({user.name})
                </button>
                {dependents.map((d) => (
                  <button
                    key={d.dependent_id}
                    data-testid={`profile-option-${d.dependent_id}`}
                    onClick={() => { setActiveProfile({ id: d.dependent_id, name: d.name }); setShowProfiles(false); }}
                    className="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-sand"
                  >
                    {d.name} <span className="text-ink-soft text-xs">({d.relation})</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          )}

          <div className="flex items-center gap-3">
            {/* Alerts */}
            <div className="relative">
              <button
                onClick={() => { setShowAlerts(!showAlerts); loadAlerts(); }}
                data-testid="alerts-bell-btn"
                className="relative p-2 rounded-full hover:bg-sand"
                style={{ transition: "background-color 0.2s ease" }}
              >
                <Bell className="h-5 w-5 text-ink-soft" />
                {unread > 0 && (
                  <span data-testid="alerts-unread-count" className="absolute -top-0.5 -right-0.5 h-4.5 min-w-[18px] px-1 rounded-full bg-terracotta text-white text-[10px] flex items-center justify-center font-bold">
                    {unread}
                  </span>
                )}
              </button>
              {showAlerts && (
                <div className="absolute right-0 mt-2 w-80 bg-white border border-line rounded-xl shadow-md p-2 z-30 max-h-96 overflow-y-auto" data-testid="alerts-panel">
                  <p className="px-3 py-2 text-xs uppercase tracking-[0.2em] text-ink-soft">Alerts</p>
                  {alerts.length === 0 && <p className="px-3 py-4 text-sm text-ink-soft">No alerts yet.</p>}
                  {alerts.map((a) => (
                    <button
                      key={a.alert_id}
                      onClick={() => markRead(a.alert_id)}
                      data-testid={`alert-row-${a.alert_id}`}
                      data-severity={a.severity}
                      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm mb-1 border ${
                        a.read ? "border-transparent text-ink-soft" : a.severity === "critical" ? "border-terracotta/40 bg-terracotta/5" : a.severity === "info" ? "border-sage/50 bg-sage/10" : "border-line bg-sand"
                      }`}
                    >
                      <span className={`text-[10px] uppercase tracking-wider font-bold ${a.severity === "critical" ? "text-terracotta" : "text-forest"}`}>
                        {a.type} · {a.severity}
                      </span>
                      <p className="mt-0.5">{a.message}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              {user.picture && <img src={user.picture} alt={user.name} className="h-8 w-8 rounded-full border border-line" />}
              <span className="text-sm font-medium hidden sm:block" data-testid="user-name">{user.name}</span>
            </div>
            <button onClick={logout} data-testid="logout-btn" className="p-2 rounded-full hover:bg-sand" style={{ transition: "background-color 0.2s ease" }}>
              <LogOut className="h-4.5 w-4.5 text-ink-soft" />
            </button>
          </div>
        </header>

        <main className="flex-1 p-6 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

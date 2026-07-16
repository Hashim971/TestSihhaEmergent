import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeProfile, setActiveProfile] = useState({ id: "self", name: "Me" });
  const [dependents, setDependents] = useState([]);

  const checkAuth = useCallback(async () => {
    try {
      const res = await api.get("/auth/me");
      setUser(res.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    // AuthCallback will exchange the session_id and establish the session first.
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    checkAuth();
  }, [checkAuth]);

  const refreshDependents = useCallback(async () => {
    try {
      const res = await api.get("/dependents");
      setDependents(res.data);
    } catch {}
  }, []);

  useEffect(() => {
    if (user) refreshDependents();
  }, [user, refreshDependents]);

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    setUser(null);
    window.location.href = "/";
  };

  return (
    <AuthContext.Provider value={{
      user, setUser, loading, logout,
      activeProfile, setActiveProfile,
      dependents, refreshDependents,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../lib/api";

const PlatformContext = createContext(null);
const TENANT_KEY = "sihha_tenant_preview";
const DEFAULT_PRIMARY = "30 63 42";
const DEFAULT_ACCENT = "177 216 183";

const hexToTriplet = (hex) => {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
  return m ? m.slice(1).map((h) => parseInt(h, 16)).join(" ") : null;
};

export function applyBrandColors(primary, accent) {
  const root = document.documentElement.style;
  root.setProperty("--brand-primary", hexToTriplet(primary) || DEFAULT_PRIMARY);
  root.setProperty("--brand-accent", hexToTriplet(accent) || DEFAULT_ACCENT);
}

export function PlatformProvider({ children }) {
  const [env, setEnv] = useState({ env: "", is_staging: false });
  const [tenant, setTenant] = useState(null);
  const [flags, setFlags] = useState(null);

  const loadTenant = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("tenant")) sessionStorage.setItem(TENANT_KEY, params.get("tenant").toUpperCase());
    const account = sessionStorage.getItem(TENANT_KEY) || undefined;
    try {
      const { data } = await api.get("/tenant", { params: { host: window.location.hostname, account } });
      setTenant(data.tenant);
      applyBrandColors(data.tenant?.primary_color, data.tenant?.accent_color);
      document.title = data.tenant ? `${data.tenant.name} — powered by Sihha AI` : "Sihha AI — Intelligent Healthcare";
      document.documentElement.lang = data.tenant?.default_language || "en";
    } catch {
      setTenant(null);
    }
  }, []);

  useEffect(() => {
    api.get("/env").then(({ data }) => {
      setEnv(data);
      document.documentElement.style.setProperty("--env-bar", data.is_staging ? "28px" : "0px");
    }).catch(() => {});
    loadTenant();
  }, [loadTenant]);

  const refreshFlags = useCallback(() => api.get("/flags").then(({ data }) => setFlags(data)).catch(() => {}), []);

  const exitTenantPreview = () => {
    sessionStorage.removeItem(TENANT_KEY);
    window.location.href = window.location.pathname;
  };

  const isOn = (key) => {
    const source = flags || tenant?.features;
    return !source || source[key] !== false;
  };

  return (
    <PlatformContext.Provider value={{ env, tenant, flags, isOn, refreshFlags, loadTenant, exitTenantPreview }}>
      {children}
    </PlatformContext.Provider>
  );
}

export const usePlatform = () => useContext(PlatformContext);

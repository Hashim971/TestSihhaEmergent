import React, { useEffect, useRef, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Activity } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash;
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      navigate("/");
      return;
    }
    const sessionId = match[1];

    (async () => {
      try {
        const res = await api.post("/auth/session", { session_id: sessionId });
        setUser(res.data);
        window.history.replaceState(null, "", "/dashboard");
        navigate("/dashboard", { state: { user: res.data }, replace: true });
      } catch (e) {
        navigate("/");
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-sand" data-testid="auth-callback-loading">
      <div className="flex flex-col items-center gap-4">
        <Activity className="h-8 w-8 text-forest animate-pulse" />
        <p className="text-ink-soft">Signing you in…</p>
      </div>
    </div>
  );
}

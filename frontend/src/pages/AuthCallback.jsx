import React, { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Leaf } from "lucide-react";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const sessionId = new URLSearchParams(location.hash.replace(/^#/, "")).get("session_id");
    if (!sessionId) {
      navigate("/auth", { replace: true });
      return;
    }
    api.post("/auth/google/session", { session_id: sessionId })
      .then(({ data }) => {
        setUser(data);
        window.history.replaceState(null, "", window.location.pathname);
        navigate(data.onboarding_completed ? "/dashboard" : "/onboarding", { replace: true });
      })
      .catch((e) => {
        const detail = e?.response?.data?.detail;
        toast.error(typeof detail === "string" ? detail : "Google sign-in failed. Please try again.");
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/auth", { replace: true });
      });
  }, [location.hash, navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-sand" data-testid="auth-callback">
      <div className="flex items-center gap-3 text-ink-soft">
        <Leaf className="h-5 w-5 text-forest animate-pulse" />
        <span className="text-sm">Signing you in…</span>
      </div>
    </div>
  );
}

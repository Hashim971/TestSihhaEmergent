import React, { useEffect, useState } from "react";
import { api, SERVICE_DOWN_EVENT } from "../lib/api";
import { CloudOff, RefreshCw } from "lucide-react";

export function ServiceUnavailable() {
  const [down, setDown] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const onDown = () => setDown(true);
    window.addEventListener(SERVICE_DOWN_EVENT, onDown);
    return () => window.removeEventListener(SERVICE_DOWN_EVENT, onDown);
  }, []);

  useEffect(() => {
    if (!down) return undefined;
    const id = setInterval(() => api.get("/health").then(() => window.location.reload()).catch(() => {}), 15000);
    return () => clearInterval(id);
  }, [down]);

  if (!down) return null;

  const retry = async () => {
    setChecking(true);
    try {
      await api.get("/health");
      window.location.reload();
    } catch {
      setChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] bg-sand/95 backdrop-blur-md flex items-center justify-center px-6"
      role="alertdialog" aria-live="assertive" data-testid="service-unavailable">
      <div className="card p-10 max-w-md text-center fade-up">
        <div className="h-12 w-12 rounded-full bg-forest mx-auto flex items-center justify-center mb-5">
          <CloudOff className="h-6 w-6 text-sage" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight mb-2">Service temporarily unavailable</h1>
        <p className="text-sm text-ink-soft mb-6">
          We can't reach Sihha AI right now. Your records are safe — nothing you saved has been lost.
          We'll reconnect automatically as soon as it's back.
        </p>
        <button onClick={retry} disabled={checking} data-testid="service-retry-btn" className="btn-primary mx-auto">
          <RefreshCw className={`h-4 w-4 ${checking ? "animate-spin" : ""}`} />
          {checking ? "Checking…" : "Try again"}
        </button>
      </div>
    </div>
  );
}

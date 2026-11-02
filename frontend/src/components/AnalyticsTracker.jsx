import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { startAnalytics, stopAnalytics, trackPage } from "../lib/analytics";

export function AnalyticsTracker() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const uid = user && !user.is_admin ? user.user_id : null;

  useEffect(() => {
    if (!uid) return undefined;
    startAnalytics(user);
    trackPage(window.location.pathname);
    return () => stopAnalytics();
    // eslint-disable-next-line
  }, [uid]);

  useEffect(() => { trackPage(pathname); }, [pathname]);
  return null;
}

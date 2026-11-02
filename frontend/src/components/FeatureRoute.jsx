import React, { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import { usePlatform } from "../context/PlatformContext";

export function FeatureRoute({ flag, children }) {
  const { isOn, flags } = usePlatform();
  const off = flags && !isOn(flag);
  useEffect(() => {
    if (off) toast.info("That feature isn't available for your organisation.");
  }, [off]);
  return off ? <Navigate to="/dashboard" replace /> : children;
}

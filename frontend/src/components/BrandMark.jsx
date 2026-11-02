import React from "react";
import { Leaf } from "lucide-react";
import { usePlatform } from "../context/PlatformContext";

const API_ORIGIN = process.env.REACT_APP_BACKEND_URL;

export function BrandMark({ size = "md", suffix = "", testid = "brand-mark" }) {
  const { tenant } = usePlatform();
  const box = size === "lg" ? "h-10 w-10" : "h-9 w-9";
  const text = size === "lg" ? "text-2xl" : "text-xl";
  return (
    <span className="flex items-center gap-2 min-w-0" data-testid={testid}>
      {tenant?.logo_url ? (
        <img src={`${API_ORIGIN}${tenant.logo_url}`} alt={tenant.name} className={`${box} rounded-full object-contain bg-white border border-line`} />
      ) : (
        <span className={`${box} rounded-full bg-forest flex items-center justify-center shrink-0`}>
          <Leaf className="h-5 w-5 text-sage" />
        </span>
      )}
      <span className={`font-heading font-bold ${text} text-forest truncate`} data-testid={`${testid}-name`}>
        {tenant?.name || "Sihha AI"}{suffix}
      </span>
    </span>
  );
}

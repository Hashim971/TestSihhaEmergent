import React from "react";
import { FlaskConical, X } from "lucide-react";
import { usePlatform } from "../context/PlatformContext";

export function StagingBar() {
  const { env, tenant, exitTenantPreview } = usePlatform();
  if (!env.is_staging) return null;
  return (
    <div className="fixed top-0 inset-x-0 z-[60] h-7 bg-[#0F172A] text-amber-300 text-[11px] font-semibold tracking-wider uppercase flex items-center justify-center gap-3 px-4"
      role="status" data-testid="staging-persistent-bar">
      <FlaskConical className="h-3.5 w-3.5" />
      <span>Staging — test environment, not production</span>
      {tenant && (
        <span className="normal-case tracking-normal font-medium text-amber-100 flex items-center gap-1.5" data-testid="tenant-preview-indicator">
          · Previewing {tenant.name} ({tenant.account_id})
          <button onClick={exitTenantPreview} data-testid="exit-tenant-preview-btn" className="p-0.5 rounded hover:bg-white/10" aria-label="Exit hospital preview">
            <X className="h-3 w-3" />
          </button>
        </span>
      )}
    </div>
  );
}

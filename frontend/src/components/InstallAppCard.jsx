import React, { useEffect, useState } from "react";
import { Smartphone, Download, Share, PlusSquare } from "lucide-react";

let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
});

const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
const isIOS = () => /iphone|ipad|ipod/i.test(window.navigator.userAgent);

export function InstallAppCard() {
  const [canPrompt, setCanPrompt] = useState(!!deferredPrompt);
  const [installed, setInstalled] = useState(isStandalone());

  useEffect(() => {
    const onPrompt = () => setCanPrompt(true);
    const onInstalled = () => setInstalled(true);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const install = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") setInstalled(true);
    deferredPrompt = null;
    setCanPrompt(false);
  };

  return (
    <div className="card p-6 flex flex-col sm:flex-row gap-5 items-start" data-testid="install-app-card">
      <div className="h-12 w-12 rounded-2xl bg-forest flex items-center justify-center shrink-0">
        <Smartphone className="h-6 w-6 text-sage" />
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold text-ink">Install the phone app</h3>
        {installed ? (
          <p className="text-sm text-ink-soft mt-1" data-testid="install-app-installed">Installed — open it from your home screen.</p>
        ) : (
          <>
            <p className="text-sm text-ink-soft mt-1">
              Add Sihha AI to your home screen. It opens full-screen like a regular app — no store download needed.
            </p>
            {canPrompt && (
              <button onClick={install} data-testid="install-app-btn" className="btn-primary mt-4">
                <Download className="h-4 w-4" /> Install app
              </button>
            )}
            {!canPrompt && (
              <ol className="mt-3 space-y-1.5 text-xs text-ink-soft" data-testid="install-app-steps">
                {isIOS() ? (
                  <>
                    <li className="flex items-center gap-2"><Share className="h-3.5 w-3.5" /> In Safari, tap the Share button</li>
                    <li className="flex items-center gap-2"><PlusSquare className="h-3.5 w-3.5" /> Choose “Add to Home Screen”</li>
                  </>
                ) : (
                  <>
                    <li>• Android (Chrome): menu ⋮ → “Install app” or “Add to Home screen”</li>
                    <li>• iPhone (Safari): Share → “Add to Home Screen”</li>
                  </>
                )}
              </ol>
            )}
          </>
        )}
      </div>
    </div>
  );
}

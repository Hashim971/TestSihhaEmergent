import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import rrwebPlayer from "rrweb-player";
import "rrweb-player/dist/style.css";
import { api } from "../../lib/api";

export function ReplayModal({ sessionId, t, onClose }) {
  const box = useRef(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let player;
    let live = true;
    api.get(`/admin/analytics/replays/${sessionId}`).then(({ data }) => {
      if (!live || !box.current) return;
      const width = Math.min(1100, window.innerWidth - 64);
      player = new rrwebPlayer({
        target: box.current,
        props: { events: data.events, width, height: Math.round(Math.min(window.innerHeight * 0.62, width * 0.6)),
          autoPlay: !t, skipInactive: true, mouseTail: false, showController: true },
      });
      if (t) player.goto(Math.max(0, t - data.events[0].timestamp - 2000), true);
    }).catch((e) => live && setError(e?.response?.data?.detail || "Could not load this recording"));
    return () => { live = false; try { player?.$destroy(); } catch {} };
  }, [sessionId, t]);

  return createPortal(
    <div className="fixed inset-0 z-50 bg-ink/60 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="card p-4 max-w-[1140px] w-full max-h-[95vh] overflow-auto fade-up" onClick={(e) => e.stopPropagation()} data-testid="replay-modal">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold">Session replay <span className="font-mono text-xs text-ink-soft">{sessionId}</span></p>
          <button onClick={onClose} className="p-1.5 rounded-full hover:bg-sand" data-testid="replay-modal-close"><X className="h-4 w-4" /></button>
        </div>
        {error ? <p className="text-sm text-terracotta" data-testid="replay-error">{error}</p> : <div ref={box} className="flex justify-center" data-testid="replay-player" />}
      </div>
    </div>,
    document.body
  );
}

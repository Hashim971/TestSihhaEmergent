import React, { useRef } from "react";
import { Camera, X } from "lucide-react";

export function ChatPhotoPicker({ photo, setPhoto, disabled }) {
  const ref = useRef(null);
  const pick = (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (photo?.previewUrl) URL.revokeObjectURL(photo.previewUrl);
    setPhoto({ file, previewUrl: URL.createObjectURL(file), keep: true });
  };
  return (
    <>
      <button type="button" onClick={() => ref.current?.click()} disabled={disabled} data-testid="chat-camera-btn"
        aria-label="Add a photo" className="h-10 w-10 shrink-0 rounded-full border border-line flex items-center justify-center hover:bg-sand disabled:opacity-50"
        style={{ transition: "background-color 0.2s ease" }}>
        <Camera className="h-4 w-4 text-forest" />
      </button>
      <input ref={ref} type="file" accept="image/jpeg,image/png,image/webp,image/*" capture="environment" className="hidden" onChange={pick} data-testid="chat-photo-input" />
    </>
  );
}

export function ChatPhotoPreview({ photo, setPhoto }) {
  if (!photo) return null;
  return (
    <div className="px-4 pt-3 flex items-center gap-3" data-testid="chat-photo-preview">
      <div className="relative">
        <img src={photo.previewUrl} alt="Attached" className="h-16 w-16 rounded-xl object-cover border border-line" />
        <button onClick={() => { URL.revokeObjectURL(photo.previewUrl); setPhoto(null); }} data-testid="chat-photo-remove" aria-label="Remove photo"
          className="absolute -top-2 -end-2 h-6 w-6 rounded-full text-white flex items-center justify-center bg-black/70"><X className="h-3 w-3" /></button>
      </div>
      <div className="flex rounded-full border border-line p-0.5 text-xs bg-white">
        {[[true, "Save with my screening"], [false, "Look once, don't keep"]].map(([val, label]) => (
          <button key={String(val)} onClick={() => setPhoto({ ...photo, keep: val })} data-testid={`chat-photo-keep-${val ? "yes" : "no"}`}
            className={`px-3 py-1.5 rounded-full ${photo.keep === val ? "bg-forest text-white" : "text-ink-soft"}`}>{label}</button>
        ))}
      </div>
    </div>
  );
}

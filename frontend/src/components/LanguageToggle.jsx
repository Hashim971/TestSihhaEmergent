import React from "react";
import { Languages } from "lucide-react";
import { useLang } from "../context/LanguageContext";

export function LanguageToggle({ className = "", testid = "language-toggle" }) {
  const { lang, setLang } = useLang();
  return (
    <button onClick={() => setLang(lang === "ar" ? "en" : "ar")} data-testid={testid} data-no-translate data-lang={lang}
      className={`inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3 py-1.5 text-xs font-semibold hover:bg-sand ${className}`}
      style={{ transition: "background-color 0.2s ease" }} aria-label="Switch language">
      <Languages className="h-3.5 w-3.5" />
      {lang === "ar" ? "English" : "العربية"}
    </button>
  );
}

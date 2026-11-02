import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import ar from "../i18n/ar.json";
import { usePlatform } from "./PlatformContext";

const LangContext = createContext({ lang: "en", setLang: () => {}, t: (s) => s });
const KEY = "sihha_lang";
const ATTRS = ["placeholder", "title", "aria-label", "alt"];
const SKIP = "script,style,textarea,code,[data-no-translate]";

const lookup = (english) => {
  const trimmed = english.replace(/\s+/g, " ").trim();
  const hit = trimmed && ar[trimmed];
  if (!hit) return null;
  return english.match(/^\s*/)[0] + hit + english.match(/\s*$/)[0];
};

function translateText(node, lang) {
  if (node.__ar !== undefined && node.nodeValue !== node.__ar) node.__en = node.nodeValue;
  const english = node.__en ?? node.nodeValue;
  if (!node.parentElement || node.parentElement.closest(SKIP)) return;
  if (lang === "ar") {
    const translated = lookup(english);
    if (translated && node.nodeValue !== translated) {
      node.__en = english;
      node.__ar = translated;
      node.nodeValue = translated;
    }
  } else if (node.__en !== undefined && node.nodeValue === node.__ar) {
    node.nodeValue = node.__en;
    node.__ar = undefined;
  }
}

function translateAttrs(el, lang) {
  if (el.closest(SKIP)) return;
  el.__enAttrs = el.__enAttrs || {};
  el.__arAttrs = el.__arAttrs || {};
  ATTRS.forEach((attr) => {
    const value = el.getAttribute(attr);
    if (value == null) return;
    if (value !== el.__arAttrs[attr]) el.__enAttrs[attr] = value;
    const english = el.__enAttrs[attr];
    const next = lang === "ar" ? lookup(english) || english : english;
    if (next !== value) {
      el.__arAttrs[attr] = lang === "ar" ? next : undefined;
      el.setAttribute(attr, next);
    }
  });
}

function translateTree(root, lang) {
  if (root.nodeType === Node.TEXT_NODE) return translateText(root, lang);
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  translateAttrs(root, lang);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.nodeType === Node.TEXT_NODE) translateText(n, lang);
    else translateAttrs(n, lang);
  }
}

export function LanguageProvider({ children }) {
  const { tenant } = usePlatform();
  const [lang, setLangState] = useState(() => localStorage.getItem(KEY) || "en");

  useEffect(() => {
    if (!localStorage.getItem(KEY) && tenant?.default_language) setLangState(tenant.default_language);
  }, [tenant]);

  const setLang = useCallback((next) => {
    localStorage.setItem(KEY, next);
    setLangState(next);
  }, []);

  useEffect(() => {
    const html = document.documentElement;
    html.lang = lang;
    html.dir = lang === "ar" ? "rtl" : "ltr";
    translateTree(document.body, lang);
    if (lang !== "ar") return undefined;
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((m) => {
        if (m.type === "characterData") translateText(m.target, lang);
        else if (m.type === "attributes") translateAttrs(m.target, lang);
        else m.addedNodes.forEach((n) => translateTree(n, lang));
      });
    });
    observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    return () => observer.disconnect();
  }, [lang]);

  const t = useCallback((s) => (lang === "ar" && ar[s]) || s, [lang]);

  return <LangContext.Provider value={{ lang, setLang, t }}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);

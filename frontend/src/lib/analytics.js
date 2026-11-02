import { record } from "rrweb";
import { api, API } from "./api";

const SID_KEY = "sihha:an-sid";
const IDLE_MS = 30 * 60 * 1000;
const INTERACTIVE = "a,button,input,select,textarea,label,summary,[role=button],[role=link],[role=tab],[role=switch],[onclick],[tabindex]";
let st = null;

const now = () => Date.now();
const normPath = (p) => p.split("/").map((s) => (/^(?=.*\d)[A-Za-z0-9_-]{6,}$/.test(s) ? ":id" : s)).join("/") || "/";

function sessionId() {
  const raw = sessionStorage.getItem(SID_KEY);
  const [sid, last] = (raw || "").split("|");
  const id = sid && now() - Number(last) < IDLE_MS ? sid : `as_${Math.random().toString(36).slice(2)}${now().toString(36)}`;
  sessionStorage.setItem(SID_KEY, `${id}|${now()}`);
  return id;
}

function describe(el) {
  const tagged = el.closest("[data-testid]");
  if (tagged) return tagged.getAttribute("data-testid").slice(0, 120);
  const ctl = el.closest("a,button");
  const label = ctl ? (ctl.getAttribute("aria-label") || ctl.innerText || "").trim().slice(0, 40) : "";
  return `${(ctl || el).tagName.toLowerCase()}${label ? `: ${label}` : ""}`;
}

function push(type, extra = {}) {
  if (!st) return;
  st.events.push({ type, path: st.path, t: now(), vw: window.innerWidth, ...extra });
}

async function flush(final = false) {
  if (!st || (!st.events.length && !st.replay.length)) return;
  const body = { session_id: st.sid, events: st.events.splice(0), replay: st.replay.splice(0), seq: st.seq++ };
  sessionStorage.setItem(SID_KEY, `${st.sid}|${now()}`);
  try {
    if (final) {
      const json = JSON.stringify(body);
      if (json.length < 60000) {
        await fetch(`${API}/analytics/collect`, { method: "POST", body: json, keepalive: true, credentials: "include", headers: { "Content-Type": "application/json" } });
        return;
      }
    }
    await api.post("/analytics/collect", body);
  } catch {}
}

function onClick(e) {
  if (!st || !(e.target instanceof Element)) return;
  const de = document.documentElement;
  const point = { x: +((e.pageX / de.scrollWidth) * 100).toFixed(2), y: Math.round(e.pageY), dh: de.scrollHeight, target: describe(e.target) };
  push("click", point);
  const t = now();
  st.clicks = st.clicks.filter((c) => t - c.t < 800 && Math.hypot(c.x - e.pageX, c.y - e.pageY) < 40);
  st.clicks.push({ t, x: e.pageX, y: e.pageY });
  if (st.clicks.length === 3) push("rage", point);
  if (!e.target.closest(INTERACTIVE) && getComputedStyle(e.target).cursor !== "pointer") push("dead", point);
}

function onHide() {
  if (document.visibilityState === "hidden") flush(true);
}

export function startAnalytics(user) {
  if (st || !user || user.is_admin) return;
  st = { sid: sessionId(), events: [], replay: [], seq: now(), clicks: [], path: null, since: now() };
  st.stopRecord = record({
    emit: (ev) => { st && st.replay.push(ev); if (st && st.replay.length > 400) flush(); },
    maskAllInputs: true,
    maskTextSelector: "main, [data-private]",
    blockSelector: "main img, video, canvas, [data-rr-block]",
    sampling: { mousemove: 150, scroll: 200, input: "last" },
    inlineStylesheet: true,
  });
  document.addEventListener("click", onClick, true);
  document.addEventListener("visibilitychange", onHide);
  st.timer = setInterval(flush, 5000);
}

export function trackPage(pathname) {
  if (!st) return;
  const path = normPath(pathname);
  if (path === st.path) return;
  if (st.path) push("leave", { duration: now() - st.since });
  st.path = path;
  st.since = now();
  push("pageview");
}

export function stopAnalytics() {
  if (!st) return;
  if (st.path) push("leave", { duration: now() - st.since });
  flush(true);
  st.stopRecord?.();
  clearInterval(st.timer);
  document.removeEventListener("click", onClick, true);
  document.removeEventListener("visibilitychange", onHide);
  st = null;
}

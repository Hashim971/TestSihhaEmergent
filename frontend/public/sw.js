const CACHE = "sihha-shell-v1";
const SHELL = ["/", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Network first; the cache is only an offline fallback. API calls and health data are never cached.
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api")) return;
  event.respondWith(
    fetch(request)
      .then((res) => {
        if (res.ok && (request.mode === "navigate" || SHELL.includes(url.pathname))) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request.mode === "navigate" ? "/" : request, copy));
        }
        return res;
      })
      .catch(() => caches.match(request.mode === "navigate" ? "/" : request)),
  );
});

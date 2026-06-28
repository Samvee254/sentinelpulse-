// Service worker: network-first for the app shell, so the installed app
// always shows the latest version when online. Falls back to the cached
// copy only when offline. Bump CACHE_NAME whenever this file changes --
// that's what makes the browser notice there's an update at all.
const CACHE_NAME = "sentinelpulse-shell-v2";
const SHELL_FILES = [
  "./",
  "./index.html",
  "./style.css",
  "./app.js",
  "./favicon.svg",
  "./icon-192.png",
  "./icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never cache API calls -- always go to the network for live data.
  if (url.hostname.includes("onrender.com")) {
    return;
  }

  // Network-first: try to fetch the latest version. Only fall back to the
  // cache if the network request fails (i.e. genuinely offline).
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

/* Service worker: cache the app shell for installability/offline load.
 * Strike data is always fetched network-first so the map stays live;
 * alerts themselves come via Telegram, never from here. */
const CACHE = "storm-map-v1";
const SHELL = [
  ".",
  "index.html",
  "style.css",
  "app.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "vendor/leaflet/leaflet.css",
  "vendor/leaflet/leaflet.js",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // Live data + map tiles: network first, no caching of tiles (keep it light).
  if (url.pathname.endsWith("strikes.json") || url.hostname.includes("openstreetmap")) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then((hit) => hit || fetch(e.request))
  );
});

/*
 * Student Finance service worker.
 *
 * Privacy rules:
 *  - Only the static app shell and the offline page are cached.
 *  - Navigation (HTML) requests always go to the network; private pages are
 *    never stored. If the network fails, the offline page is shown instead.
 *  - Non-GET requests and cross-origin requests are never touched.
 */
const CACHE_NAME = "student-finance-{{ cache_version }}";
const OFFLINE_URL = "{{ offline_url }}";
const STATIC_ASSETS = [
{% for asset in static_assets %}  "{{ asset|escapejs }}",
{% endfor %}];
const PRECACHE = STATIC_ASSETS.concat([OFFLINE_URL]);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("student-finance-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }

  // Page navigations: network only, offline page as fallback. Never cached.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match(OFFLINE_URL))
    );
    return;
  }

  // Cache-first only for the explicitly listed static files.
  if (STATIC_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
  }
  // Everything else (JSON chart data, exports, etc.) goes straight to the network.
});

self.addEventListener("message", (event) => {
  if (event.data === "clear-caches") {
    caches.keys().then((keys) => keys.forEach((key) => caches.delete(key)));
  }
});

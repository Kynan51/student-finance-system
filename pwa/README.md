# PWA files

The roadmap lists `pwa/manifest.webmanifest` and `pwa/service-worker.js`. In this
project they are served by Django so that:

* the service worker is served from the site root (`/service-worker.js`) and can
  control the whole app (a worker under `/static/js/` could only control `/static/js/`);
* the list of cached files uses Django's `static()` URLs, which stay correct when
  production adds content hashes to file names.

| What | Source file | Served at |
|---|---|---|
| Web app manifest | `templates/core/manifest.webmanifest` | `/manifest.webmanifest` |
| Service worker | `templates/core/service-worker.js` | `/service-worker.js` |
| Offline page | `templates/core/offline.html` | `/offline/` |
| Registration + install button | `static/js/pwa-register.js` | `/static/js/pwa-register.js` |
| Icons | `static/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png` | `/static/icons/...` |
| Cache version | `PWA_CACHE_VERSION` in `core/views.py` | bump it when static files change |

Caching policy: only the app shell (CSS, core JS, icons) and the offline page are
cached. Page navigations always go to the network and are never stored; JSON chart
data, reports and every authenticated page are never cached. Signed-in responses
also carry `Cache-Control: no-store, private` (see `core/middleware.py`).

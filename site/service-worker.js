const CACHE_NAME = "tennis-entry-watch-52335e698438";
const PRECACHE_URLS = [
  "./archive/index.html",
  "./assets/icons/apple-touch-icon.png",
  "./assets/icons/favicon-48.png",
  "./assets/icons/icon-192.png",
  "./assets/icons/icon-512.png",
  "./index.html",
  "./install/index.html",
  "./manifest.webmanifest",
  "./pwa.js",
  "./schedules/index.html",
  "./tournaments/aon-open-challenger-2026.html",
  "./tournaments/augsburg-challenger-2026.html",
  "./tournaments/cancun-challenger-2026.html",
  "./tournaments/cassis-open-provence-2026.html",
  "./tournaments/challenger-de-buenos-aires-2026.html",
  "./tournaments/chengdu-open-2026.html",
  "./tournaments/cincinnati-open-2026.html",
  "./tournaments/citta-di-biella-2026.html",
  "./tournaments/como-challenger-2026.html",
  "./tournaments/copa-sevilla-2026.html",
  "./tournaments/genoa-challenger-2026.html",
  "./tournaments/guangzhou-huangpu-international-tennis-open-2026.html",
  "./tournaments/hamburg-ladies-gents-cup-2026.html",
  "./tournaments/hangzhou-open-2026.html",
  "./tournaments/indiana-hardcourt-championships-2026.html",
  "./tournaments/internazionali-di-tennis-citta-di-todi-2026.html",
  "./tournaments/istanbul-challenger-2026.html",
  "./tournaments/kingston-1-challenger-2026.html",
  "./tournaments/kingston-2-challenger-2026.html",
  "./tournaments/manacor-challenger-2026.html",
  "./tournaments/no-open-2026.html",
  "./tournaments/open-de-rennes-2026.html",
  "./tournaments/phan-thiet-challenger-iii-2026.html",
  "./tournaments/phan-thiet-challenger-iv-2026.html",
  "./tournaments/plovdiv-3-challenger-2026.html",
  "./tournaments/plovdiv-challenger-iv-2026.html",
  "./tournaments/porto-1-challenger-2026.html",
  "./tournaments/prague-challenger-2026.html",
  "./tournaments/president-s-cup-2026.html",
  "./tournaments/quebec-city-challenger-2026.html",
  "./tournaments/roehampton-1-challenger-2026.html",
  "./tournaments/roehampton-2-challenger-2026.html",
  "./tournaments/saint-tropez-open-2026.html",
  "./tournaments/san-diego-challenger-2026.html",
  "./tournaments/shanghai-challenger-2026.html",
  "./tournaments/sion-challenger-2026.html",
  "./tournaments/szczecin-open-2026.html",
  "./tournaments/tiburon-challenger-2026.html",
  "./tournaments/us-open-2026.html",
  "./tournaments/winston-salem-open-2026.html",
  "./tournaments/zhangjiagang-challenger-2026.html"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

async function cachedNavigation(request) {
  const cache = await caches.open(CACHE_NAME);
  const direct = await cache.match(request);
  if (direct) return direct;
  const url = new URL(request.url);
  if (url.pathname.endsWith("/")) {
    url.pathname += "index.html";
    const directoryIndex = await cache.match(url.toString());
    if (directoryIndex) return directoryIndex;
  }
  return cache.match("./index.html");
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => cachedNavigation(request))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      }
      return response;
    }))
  );
});

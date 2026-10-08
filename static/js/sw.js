/* CarHub service worker: installable app + an offline page. Pages are always fetched fresh from the
   network (prices, stock and trips change constantly); only static assets are cached. */
const VERSION = 'carhub-v1';
const OFFLINE = '/offline/';
const PRECACHE = [OFFLINE, '/static/img/pwa/icon-192.png', '/static/img/favicon.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;                 // map tiles, fonts, photos: browser default
  if (req.mode === 'navigate') {                              // pages: network first, offline page as fallback
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
    return;
  }
  if (url.pathname.startsWith('/static/')) {                  // assets: serve cached, refresh in background
    event.respondWith(caches.open(VERSION).then(async (cache) => {
      const hit = await cache.match(req);
      const fresh = fetch(req).then((res) => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => hit);
      return hit || fresh;
    }));
  }
});

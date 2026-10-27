// Offline app shell: pages and assets are cached as they are used, so the visit form opens without network.
// API calls are never cached (data must stay fresh); offline visits are queued by the app itself.
const CACHE = 'shikshapulse-v1'
self.addEventListener('install', (e) => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then((c) => c.addAll(['/']))) })
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()))
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return
  e.respondWith(
    fetch(e.request).then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return res })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('/')))
  )
})

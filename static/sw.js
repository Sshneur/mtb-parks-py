var CACHE_NAME = 'mtb-parks-__CACHE_VERSION__';
var API_CACHE = 'mtb-parks-api-__CACHE_VERSION__';

var SHELL_URLS = [
  '/', '/css/style.css', '/js/app.js', '/js/park.js',
  '/lib/leaflet.css', '/lib/leaflet.js',
  '/manifest.json', '/map', '/development', '/contacts'
];

self.addEventListener('install', function(event) {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(SHELL_URLS);
    })
  );
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(names) {
      return Promise.all(
        names.map(function(n) {
          if (n !== CACHE_NAME && n !== API_CACHE) return caches.delete(n);
        })
      );
    }).then(function() {
      return clients.claim();
    })
  );
});

self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/')) {
    var personal = url.pathname.startsWith('/api/user/') ||
                   url.pathname.startsWith('/api/vote/my') ||
                   url.pathname.startsWith('/api/admin/');
    if (event.request.method === 'GET' && !personal) {
      event.respondWith(networkFirst(event.request));
    }
    return;
  }
  if (SHELL_URLS.includes(url.pathname) || url.pathname.startsWith('/photos/')) {
    event.respondWith(cacheFirst(event.request));
    return;
  }
  event.respondWith(networkFirst(event.request));
});

function cacheFirst(request) {
  return caches.match(request).then(function(cached) {
    return cached || fetch(request).then(function(response) {
      var clone = response.clone();
      caches.open(CACHE_NAME).then(function(cache) { cache.put(request, clone); });
      return response;
    });
  });
}

function networkFirst(request) {
  return fetch(request).then(function(response) {
    if (response.ok && request.method === 'GET') {
      var clone = response.clone();
      caches.open(API_CACHE).then(function(cache) { cache.put(request, clone); });
    }
    return response;
  }).catch(function() {
    return caches.match(request).then(function(cached) {
      if (cached) return cached;
      if (request.destination === 'document') {
        return caches.match('/');
      }
      return new Response('', { status: 503 });
    });
  });
}
var CACHE_NAME = 'mtb-parks-__CACHE_VERSION__';
var API_CACHE = 'mtb-parks-api-__CACHE_VERSION__';
var ANALYTICS_QUEUE = 'mtb-parks-analytics-queue';

var SHELL_URLS = [
  '/', '/css/style.css', '/js/app.js', '/js/park.js',
  '/lib/leaflet.css', '/lib/leaflet.js',
  '/manifest.json', '/map', '/development', '/contacts',
  '/x.js'
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
          if (n !== CACHE_NAME && n !== API_CACHE && n !== ANALYTICS_QUEUE) return caches.delete(n);
        })
      );
    }).then(function() {
      return clients.claim();
    })
  );
});

// ===== OFFLINE ANALYTICS QUEUE =====
function queueAnalyticsEvent(eventData) {
  return caches.open(ANALYTICS_QUEUE).then(function(cache) {
    var id = Date.now() + '-' + Math.random().toString(36).slice(2, 8);
    var request = new Request('/analytics-queue/' + id, { method: 'PUT' });
    var response = new Response(JSON.stringify(eventData), {
      headers: { 'Content-Type': 'application/json' }
    });
    return cache.put(request, response);
  });
}

function flushAnalyticsQueue() {
  return caches.open(ANALYTICS_QUEUE).then(function(cache) {
    return cache.keys().then(function(keys) {
      return Promise.all(keys.map(function(key) {
        return cache.match(key).then(function(response) {
          return response.json();
        }).then(function(data) {
          return fetch('/api/x', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
            keepalive: true
          }).then(function() {
            return cache.delete(key);
          }).catch(function() {
            // Оставляем в очереди, попробуем позже
          });
        });
      }));
    });
  });
}

self.addEventListener('online', function() {
  flushAnalyticsQueue();
});

setInterval(function() {
  flushAnalyticsQueue();
}, 60000);

self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);

  // Перехват Umami запросов — буферизуем при offline
  if (url.hostname === 'stats.gripcheck.ru' || url.pathname === '/x.js' || url.pathname === '/api/x') {
    if (event.request.method === 'POST') {
      event.respondWith(
        fetch(event.request.clone()).catch(function() {
          return event.request.clone().json().then(function(body) {
            return queueAnalyticsEvent(body).then(function() {
              return new Response('', { status: 202 });
            });
          }).catch(function() {
            return new Response('', { status: 202 });
          });
        })
      );
      return;
    }
    event.respondWith(
      fetch(event.request).catch(function() {
        return caches.match(event.request);
      })
    );
    return;
  }

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
const CACHE_NAME = 'ledgerflow-cache-v1';
const urlsToCache = [
  './',
  './index.html', // This path might vary depending on Streamlit's internal routing
  // You might need to add other static assets your app serves directly,
  // though Streamlit often bundles most assets.
  // './static/your-custom-css.css', // Example
  // './static/your-custom-js.js',  // Example
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});

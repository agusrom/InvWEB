const CACHE_NAME = "inventory-mobile-v843";
const APP_SHELL = [
    "/static/css/mobile_count.css?v=843",
    "/static/js/mobile_count.js?v=843",
    "/static/css/mobile_home.css?v=823",
    "/static/css/mobile_home_v826.css?v=829",
    "/static/js/mobile_home.js?v=835",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => key.startsWith("inventory-mobile-") && key !== CACHE_NAME)
                .map((key) => caches.delete(key))
        ))
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") return;
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;
    const mobileRequest = url.pathname.endsWith("/movil")
        || url.pathname.includes("/conteo-movil")
        || url.pathname.includes("mobile_count")
        || url.pathname.includes("mobile_home");
    if (!mobileRequest) return;
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response.ok) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                }
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});

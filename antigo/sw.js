// Service worker simples do Invest.
// - Dados (data/*.json): SEMPRE da rede, nunca do cache — para nunca mostrar dados velhos.
// - App (index.html, manifesto, ícones): rede primeiro; o cache só é usado se estiver offline.
const CACHE = 'invest-app-v1';
const APP = ['./', 'index.html', 'manifest.webmanifest', 'icone.svg', 'icone-192.png', 'icone-512.png'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE).then(c => c.addAll(APP)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
    e.waitUntil(caches.keys()
        .then(nomes => Promise.all(nomes.filter(n => n !== CACHE).map(n => caches.delete(n))))
        .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url);
    if (e.request.method !== 'GET' || url.origin !== location.origin) return; // CDNs: navegador cuida
    if (url.pathname.includes('/data/')) return;                               // dados: direto da rede
    e.respondWith(
        fetch(e.request)
            .then(resp => {
                if (resp.ok) { const copia = resp.clone(); caches.open(CACHE).then(c => c.put(e.request, copia)); }
                return resp;
            })
            .catch(() => caches.match(e.request).then(r => r || caches.match('index.html')))
    );
});

const CACHE='clubdailyfive-v17-reminders';
const CORE=['/assets/game-hub.css?v=20261007-11','/assets/games/daily-five-560.webp','/assets/games/player-wordle-560.webp','/','/offline.html','/manifest.webmanifest','/pwa.js','/assets/favicon.svg','/assets/icon-192.png','/assets/icon-512.png','/assets/clubdailyfive-logo.svg','/assets/site-header.css?v=2'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting())));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',event=>{const request=event.request;if(request.method!=='GET')return;const url=new URL(request.url);if(url.origin!==location.origin||url.pathname.startsWith('/owner-stats')||url.pathname==='/track.php')return;if(request.mode==='navigate'){event.respondWith(fetch(request).then(response=>{const copy=response.clone();if(response.ok)caches.open(CACHE).then(cache=>cache.put(request,copy));return response}).catch(async()=>await caches.match(request)||caches.match('/offline.html')));return}if(/\.(?:css|js|png|svg|webp|jpg|webmanifest)$/.test(url.pathname))event.respondWith(caches.match(request).then(cached=>cached||fetch(request).then(response=>{if(response.ok)caches.open(CACHE).then(cache=>cache.put(request,response.clone()));return response})));});

// Daily reminders (Web Push).
self.addEventListener('push',event=>{let d={};try{d=event.data?event.data.json():{}}catch(e){}
 const title=d.title||'Today’s Daily Five is ready';
 event.waitUntil(self.registration.showNotification(title,{body:d.body||'',icon:'/assets/icon-192.png',badge:'/assets/icon-192.png',tag:d.tag||'daily-five',data:{url:d.url||'/daily-football-quiz'}}));});
self.addEventListener('notificationclick',event=>{event.notification.close();const url=new URL((event.notification.data&&event.notification.data.url)||'/',self.location.origin).href;
 event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{for(const c of list){if(c.url.split('?')[0]===url.split('?')[0]&&'focus' in c)return c.focus()}return clients.openWindow(url)}));});

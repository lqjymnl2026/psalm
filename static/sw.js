/* 赞美诗中心 Service Worker —— 仅用于满足 PWA 可安装条件（安卓 Chrome「安装应用」）。
   不缓存、不拦截任何请求，彻底避免旧代码被缓存的问题。 */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => { /* 不拦截、不缓存 */ });

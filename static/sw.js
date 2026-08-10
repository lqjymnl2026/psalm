/* 赞美诗中心：不再使用离线缓存（本地服务不需要）。
   本文件只负责：清理旧缓存 → 注销自身 → 刷新所有打开的页面，彻底解决旧代码被缓存的问题。 */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.registration.unregister())
      .then(() => self.clients.matchAll({ type: "window" }))
      .then((cls) => cls.forEach((c) => c.navigate(c.url)))
  );
});
// 不再拦截任何网络请求

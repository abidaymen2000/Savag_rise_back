# Savage Rise analytics frontend examples

Use the public endpoint `POST /analytics/events` for client-side actions that only the browser can see.

```js
srTrack("product_viewed", {
  product_id: "sr-notte-oversized-tee",
  product_name: "SR NOTTE OVERSIZED TEE"
});

srTrack("notify_me_clicked", {
  product_id: "sr-notte-oversized-tee",
  drop_date: "2026-06-25T19:00:00+02:00"
});

srTrack("button_clicked", {
  button_id: "home-hero-shop-now",
  label: "Shop now",
  page_path: window.location.pathname
});
```

For the CMS traffic page, send these fields when available:

```js
srTrack("page_viewed", {
  page_path: window.location.pathname,
  page_title: document.title,
  url: window.location.href,
  source: new URLSearchParams(window.location.search).get("utm_source"),
  utm_campaign: new URLSearchParams(window.location.search).get("utm_campaign")
});

srTrack("button_clicked", {
  button_id: "product-notify-me",
  label: "Notify me",
  page_path: window.location.pathname,
  product_id: "sr-notte-oversized-tee"
});
```

CMS traffic endpoints:

```txt
GET /admin/traffic/dashboard
GET /admin/traffic/overview
GET /admin/traffic/timeseries?metric=visitors&interval=day
GET /admin/traffic/breakdown
GET /admin/traffic/sources
GET /admin/traffic/pages
GET /admin/traffic/buttons
GET /admin/traffic/products
GET /admin/traffic/funnel
GET /admin/traffic/recent-events
```

Suggested lightweight helper:

```js
async function srTrack(eventName, metadata = {}) {
  const anonymousId = localStorage.getItem("sr_anonymous_id") || crypto.randomUUID();
  localStorage.setItem("sr_anonymous_id", anonymousId);

  const sessionId = sessionStorage.getItem("sr_session_id") || crypto.randomUUID();
  sessionStorage.setItem("sr_session_id", sessionId);

  try {
    await fetch(`${API_URL}/analytics/events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({
        event_name: eventName,
        anonymous_id: anonymousId,
        session_id: sessionId,
        product_id: metadata.product_id,
        order_id: metadata.order_id,
        source: metadata.source,
        utm_campaign: metadata.utm_campaign,
        metadata
      })
    });
  } catch (_) {
    // Analytics must never block the shopping experience.
  }
}
```

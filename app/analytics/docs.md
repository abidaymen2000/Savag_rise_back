# Savage Rise analytics frontend examples

Use the public endpoint `POST /analytics/events` for client-side actions that only the browser can see.
Use `GET /analytics/events/catalog` to retrieve the full event contract used by the CMS.

Core fields accepted by `POST /analytics/events`:

```json
{
  "event_name": "button_clicked",
  "anonymous_id": "browser-stable-id",
  "session_id": "tab-session-id",
  "product_id": "optional-product-id",
  "order_id": "optional-order-id",
  "page_path": "/products/sr-tee",
  "page_title": "SR Tee",
  "action_target": "product-add-to-cart",
  "source": "instagram",
  "utm_source": "instagram",
  "utm_medium": "paid_social",
  "utm_campaign": "drop-01",
  "metadata": {}
}
```

The backend normalizes these fields for CMS filters:

```txt
event_category, page_path, page_title, action_target, device_type,
source, utm_source, utm_medium, utm_campaign, has_account
```

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
GET /admin/traffic/all-data?page=1&page_size=100
GET /admin/traffic/realtime?window_minutes=1
GET /admin/traffic/overview
GET /admin/traffic/timeseries?metric=visitors&interval=day
GET /admin/traffic/breakdown
GET /admin/traffic/sources
GET /admin/traffic/pages
GET /admin/traffic/buttons
GET /admin/traffic/products
GET /admin/traffic/funnel
GET /admin/traffic/recent-events
GET /admin/traffic/events?page=1&page_size=50
```

Use `GET /admin/traffic/all-data` as the main CMS bootstrap call. It returns KPI cards,
funnel, chart series, source/device/account breakdowns, pages, buttons, products, recent
events, and a paginated raw events table in one response. Use `GET /admin/traffic/realtime?window_minutes=1`
for live widgets and refresh it every few seconds from the CMS.

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
        page_path: metadata.page_path || window.location.pathname,
        page_title: metadata.page_title || document.title,
        action_target: metadata.action_target || metadata.button_id || metadata.link_id || metadata.form_id,
        source: metadata.source,
        utm_source: metadata.utm_source,
        utm_medium: metadata.utm_medium,
        utm_campaign: metadata.utm_campaign,
        metadata
      })
    });
  } catch (_) {
    // Analytics must never block the shopping experience.
  }
}
```

Recommended storefront events:

```txt
page_viewed
collection_viewed
search_submitted
filter_applied
sort_changed
product_viewed
product_image_viewed
variant_selected
size_selected
color_selected
size_guide_opened
add_to_cart
remove_from_cart
cart_viewed
cart_updated
checkout_started
shipping_info_submitted
payment_started
payment_failed
button_clicked
link_clicked
form_started
form_submitted
form_error
```

Backend-tracked critical events:

```txt
account_created
email_verified
login
wishlist_added
wishlist_removed
review_created
contact_submitted
vlog_episode_viewed
coupon_applied
payment_success
order_completed
order_cancelled
```

# Progressive Web App

## Generated files

The Python site build owns the PWA output. Do not edit these files directly under `site/`:

- `manifest.webmanifest`
- `service-worker.js`
- `pwa.js`
- `install/index.html`
- `assets/icons/*`

The source icons live in `assets/pwa/`. PWA generation is implemented in `src/tennis_entry_watch/site/pwa.py` and invoked after every HTML page has been written, allowing the service worker cache version to include the complete generated snapshot.

## Update strategy

HTML navigation is network-first. When online, the user receives the latest deployed page and that response refreshes the runtime cache. When offline, the worker serves the matching cached page, normalizes directory URLs to `index.html`, and finally falls back to the cached tournament dashboard.

Static same-origin requests are cache-first. Each service worker contains a content-derived cache name, activates immediately, removes obsolete Tennis Entry Watch caches, and claims open clients.

## Installation

- Android: open the deployed site in Chrome and choose **Install app** or **Add to Home screen**.
- iPhone/iPad: open the deployed site in Safari, use **Share**, then **Add to Home Screen**.
- Installed mode is detected with the `display-mode: standalone` media query and `navigator.standalone` fallback.

The PWA currently has no push subscription backend. Notification permission is therefore never requested.

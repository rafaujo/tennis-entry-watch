import hashlib
import json
import shutil
from pathlib import Path


APP_NAME = "Tennis Entry Watch"
THEME_COLOR = "#10283d"
BACKGROUND_COLOR = "#edf2f5"

ICON_FILES = (
    "icon-1024.png",
    "icon-512.png",
    "icon-192.png",
    "apple-touch-icon.png",
    "favicon-48.png",
)

PWA_JAVASCRIPT = r"""(() => {
  const script = document.currentScript;
  const base = script?.dataset.base || "";

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", async () => {
      try {
        const registration = await navigator.serviceWorker.register(`${base}service-worker.js`);
        registration.update();
      } catch (error) {
        console.warn("PWA service worker registration failed", error);
      }
    });
  }

  const standalone = window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
  const installButton = document.querySelector("[data-install-app]");
  const installedMessage = document.querySelector("[data-installed-message]");
  let installPrompt = null;

  if (standalone) {
    if (installButton) installButton.hidden = true;
    if (installedMessage) installedMessage.hidden = false;
    document.documentElement.dataset.displayMode = "standalone";
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    if (installButton && !standalone) {
      installButton.hidden = false;
      installButton.disabled = false;
    }
  });

  installButton?.addEventListener("click", async () => {
    if (!installPrompt) return;
    installButton.disabled = true;
    await installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
  });

  window.addEventListener("appinstalled", () => {
    if (installButton) installButton.hidden = true;
    if (installedMessage) installedMessage.hidden = false;
  });
})();
"""


def pwa_head(base_href: str = "") -> str:
    return (
        f'<meta name="theme-color" content="{THEME_COLOR}">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
        f'<meta name="apple-mobile-web-app-title" content="{APP_NAME}">'
        f'<link rel="manifest" href="{base_href}manifest.webmanifest">'
        f'<link rel="icon" type="image/png" sizes="48x48" href="{base_href}assets/icons/favicon-48.png">'
        f'<link rel="apple-touch-icon" sizes="180x180" href="{base_href}assets/icons/apple-touch-icon.png">'
        f'<script defer src="{base_href}pwa.js" data-base="{base_href}"></script>'
    )


def _manifest() -> dict:
    return {
        "id": "./",
        "name": APP_NAME,
        "short_name": "Entry Watch",
        "description": "ATP entry lists, alternates, qualifying paths and withdrawals before the draw.",
        "lang": "en",
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "orientation": "any",
        "background_color": BACKGROUND_COLOR,
        "theme_color": THEME_COLOR,
        "categories": ["sports", "news", "utilities"],
        "icons": [
            {
                "src": "assets/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "assets/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
        "shortcuts": [
            {
                "name": "Tournaments",
                "short_name": "Tournaments",
                "url": "./",
                "icons": [{"src": "assets/icons/icon-192.png", "sizes": "192x192"}],
            },
            {
                "name": "Player schedules",
                "short_name": "Schedules",
                "url": "./schedules/",
                "icons": [{"src": "assets/icons/icon-192.png", "sizes": "192x192"}],
            },
        ],
    }


def _cache_version(output_dir: Path, relative_paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(relative_paths):
        path = output_dir / relative
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def _service_worker(version: str, relative_paths: list[str]) -> str:
    urls = [f"./{path}" for path in relative_paths]
    return f"""const CACHE_NAME = "tennis-entry-watch-{version}";
const PRECACHE_URLS = {json.dumps(urls, ensure_ascii=False, indent=2)};

self.addEventListener("install", (event) => {{
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)));
  self.skipWaiting();
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
}});

async function cachedNavigation(request) {{
  const cache = await caches.open(CACHE_NAME);
  const direct = await cache.match(request);
  if (direct) return direct;
  const url = new URL(request.url);
  if (url.pathname.endsWith("/")) {{
    url.pathname += "index.html";
    const directoryIndex = await cache.match(url.toString());
    if (directoryIndex) return directoryIndex;
  }}
  return cache.match("./index.html");
}}

self.addEventListener("fetch", (event) => {{
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {{
    event.respondWith(
      fetch(request)
        .then((response) => {{
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        }})
        .catch(() => cachedNavigation(request))
    );
    return;
  }}

  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {{
      if (response.ok) {{
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
      }}
      return response;
    }}))
  );
}});
"""


def write_pwa_files(
    output_dir: Path,
    asset_source: Path,
    generated_paths: list[Path],
) -> list[Path]:
    missing = [name for name in ICON_FILES if not (asset_source / name).exists()]
    if missing:
        raise ValueError(f"missing PWA icon assets under {asset_source}: {', '.join(missing)}")

    icon_dir = output_dir / "assets" / "icons"
    icon_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in ICON_FILES:
        destination = icon_dir / name
        shutil.copy2(asset_source / name, destination)
        written.append(destination)

    manifest_path = output_dir / "manifest.webmanifest"
    manifest_path.write_text(
        json.dumps(_manifest(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    written.append(manifest_path)

    script_path = output_dir / "pwa.js"
    script_path.write_text(PWA_JAVASCRIPT, encoding="utf-8")
    written.append(script_path)

    cache_paths = sorted(
        {
            path.relative_to(output_dir).as_posix()
            for path in [*generated_paths, *written]
            if path.is_file() and path.name != "icon-1024.png"
        }
    )
    version = _cache_version(output_dir, cache_paths)
    service_worker_path = output_dir / "service-worker.js"
    service_worker_path.write_text(
        _service_worker(version, cache_paths),
        encoding="utf-8",
    )
    written.append(service_worker_path)
    return written

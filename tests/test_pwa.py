import json
import struct
from pathlib import Path

from tennis_entry_watch.site.build import build_site


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def test_build_emits_installable_pwa_assets(tmp_path):
    written = build_site(Path("data/entries"), tmp_path)
    manifest_path = tmp_path / "manifest.webmanifest"
    worker_path = tmp_path / "service-worker.js"

    assert manifest_path in written
    assert worker_path in written
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["name"] == "Tennis Entry Watch"
    assert manifest["start_url"] == "./"
    assert manifest["scope"] == "./"
    assert manifest["display"] == "standalone"
    assert {icon["sizes"] for icon in manifest["icons"]} == {"192x192", "512x512"}

    assert _png_dimensions(tmp_path / "assets" / "icons" / "icon-192.png") == (192, 192)
    assert _png_dimensions(tmp_path / "assets" / "icons" / "icon-512.png") == (512, 512)
    assert _png_dimensions(tmp_path / "assets" / "icons" / "apple-touch-icon.png") == (180, 180)


def test_every_generated_page_registers_pwa_with_correct_relative_paths(tmp_path):
    build_site(Path("data/entries"), tmp_path)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    tournament = (tmp_path / "tournaments" / "us-open-2026.html").read_text(encoding="utf-8")
    schedules = (tmp_path / "schedules" / "index.html").read_text(encoding="utf-8")
    install = (tmp_path / "install" / "index.html").read_text(encoding="utf-8")

    assert 'href="manifest.webmanifest"' in index
    assert 'src="pwa.js" data-base=""' in index
    for nested in (tournament, schedules, install):
        assert 'href="../manifest.webmanifest"' in nested
        assert 'src="../pwa.js" data-base="../"' in nested
    assert "Add to Home Screen" in install
    assert "data-install-app" in install


def test_service_worker_precaches_pages_and_uses_network_first_navigation(tmp_path):
    build_site(Path("data/entries"), tmp_path)
    worker = (tmp_path / "service-worker.js").read_text(encoding="utf-8")
    assert 'const CACHE_NAME = "tennis-entry-watch-' in worker
    assert '"./index.html"' in worker
    assert '"./install/index.html"' in worker
    assert '"./tournaments/us-open-2026.html"' in worker
    assert 'request.mode === "navigate"' in worker
    assert "fetch(request)" in worker
    assert ".catch(() => cachedNavigation(request))" in worker

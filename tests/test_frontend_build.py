from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_build_artifacts_exist() -> None:
    index = ROOT / "frontend" / "dist" / "index.html"
    assert index.exists(), "Run `pnpm --filter icx-dashboard-frontend build` first."
    html = index.read_text(encoding="utf-8")
    assert '<div id="root"></div>' in html
    assert "/assets/" in html


def test_png_export_hook_is_present() -> None:
    source = (ROOT / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "toPng" in source
    assert "Export PNG" in source
    assert 'id="page-export"' in source


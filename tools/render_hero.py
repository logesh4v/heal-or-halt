"""Render docs/assets/hero.html to docs/assets/hero.png (3200x1600, 2x) with the installed Chrome."""

from pathlib import Path

from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parents[1] / "docs" / "assets"

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 800}, device_scale_factor=2)
    page.goto((ASSETS / "hero.html").as_uri())
    page.screenshot(path=str(ASSETS / "hero.png"))
    browser.close()
print(ASSETS / "hero.png")

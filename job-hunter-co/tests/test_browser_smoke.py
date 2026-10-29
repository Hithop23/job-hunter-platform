"""Smoke test: valida Playwright + Chromium en este intérprete (riesgo F1)."""

import pytest


def test_chromium_smoke():
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as exc:
            if "Executable doesn't exist" in str(exc):
                pytest.skip("Chromium no instalado")
            raise
        try:
            page = browser.new_page()
            page.goto("data:text/html,<title>JHC</title><h1>ok</h1>")
            assert page.title() == "JHC"
            assert page.inner_text("h1") == "ok"
        finally:
            browser.close()

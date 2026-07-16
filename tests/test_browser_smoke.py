"""Small, deterministic browser check for the built application."""

import os

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.skipif(
    not os.getenv('MYND_BROWSER_BASE_URL'),
    reason='requires a running application and MYND_BROWSER_BASE_URL',
)


def test_login_page_loads_without_browser_errors():
    base_url = os.getenv('MYND_BROWSER_BASE_URL', 'http://127.0.0.1:3000').rstrip('/')
    page_errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.add_init_script("localStorage.setItem('mynd_language', 'en')")

        response = page.goto(f'{base_url}/login.html', wait_until='networkidle')

        assert response is not None and response.ok
        expect(page).to_have_title('MYND - Local-first AI Workspace')
        expect(page.get_by_role('heading', name='MYND')).to_be_visible()
        expect(page.locator('#login-user')).to_be_visible()
        expect(page.locator('#login-pass')).to_be_visible()
        assert page_errors == []
        browser.close()

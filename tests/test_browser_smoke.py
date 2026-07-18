"""Small, deterministic browser check for the built application."""

import os

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.skipif(
    not os.getenv('MYND_BROWSER_BASE_URL'),
    reason='requires a running application and MYND_BROWSER_BASE_URL',
)


def test_application_entry_loads_without_browser_errors():
    base_url = os.getenv('MYND_BROWSER_BASE_URL', 'http://127.0.0.1:3000').rstrip('/')
    page_errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        page.route(
            '**/api/setup/status',
            lambda route: route.fulfill(json={'success': True, 'needs_setup': False}),
        )
        page.add_init_script("localStorage.setItem('mynd_language', 'en')")

        response = page.goto(f'{base_url}/login', wait_until='networkidle')

        assert response is not None and response.ok
        if page.title().strip() == 'MYND Setup | MYND':
            expect(page.get_by_role('heading', name='Start wählen')).to_be_visible()
        else:
            expect(page).to_have_title('MYND - Local-first AI Workspace')
            expect(page.get_by_role('heading', name='MYND')).to_be_visible()
            expect(page.locator('#login-user')).to_be_visible()
            expect(page.locator('#login-pass')).to_be_visible()
        assert page_errors == []
        browser.close()


def test_unauthenticated_root_stays_public_and_offers_sign_in():
    base_url = os.getenv('MYND_BROWSER_BASE_URL', 'http://127.0.0.1:3000').rstrip('/')
    page_errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(service_workers='block')
        context.clear_cookies()
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        def fulfill_unauthenticated_api(route):
            if route.request.url.endswith('/api/setup/status'):
                payload = {'success': True, 'needs_setup': False}
            elif route.request.url.endswith('/api/auth/me'):
                payload = {'authenticated': False, 'user': None}
            else:
                payload = {'success': True}
            route.fulfill(json=payload)

        page.route('**/api/**', fulfill_unauthenticated_api)
        page.add_init_script(
            """
            localStorage.clear();
            sessionStorage.clear();
            localStorage.setItem('mynd_token_v1', 'deliberately-invalid-smoke-token');
            localStorage.removeItem('mynd_language');
            """
        )

        response = page.goto(f'{base_url}/', wait_until='networkidle')

        assert response is not None and response.ok
        expect(page).to_have_url(f'{base_url}/')
        public_landing = page.locator('.lp[data-auth-view="public"]')
        expect(public_landing).to_be_visible()
        sign_in = page.get_by_test_id('landing-login')
        expect(sign_in).to_have_count(1)
        expect(sign_in).to_have_attribute('href', '/login')
        expect(page.locator('[data-auth-view="workspace"]')).to_have_count(0)
        assert page_errors == []
        browser.close()


def test_authenticated_user_can_create_new_chats_from_empty_state():
    base_url = os.getenv('MYND_BROWSER_BASE_URL', 'http://127.0.0.1:3000').rstrip('/')
    page_errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(service_workers='block')
        context.clear_cookies()
        page = context.new_page()
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        def fulfill_authenticated_api(route):
            if route.request.url.endswith('/api/setup/status'):
                payload = {'success': True, 'needs_setup': False}
            elif route.request.url.endswith('/api/auth/me'):
                payload = {
                    'authenticated': True,
                    'user': {'id': 'browser-smoke', 'username': 'browser-smoke', 'role': 'admin'},
                }
            else:
                payload = {'success': True}
            route.fulfill(json=payload)

        page.route('**/api/**', fulfill_authenticated_api)
        page.add_init_script(
            """
            localStorage.setItem('mynd_language', 'en');
            localStorage.setItem('mynd_token_v1', 'browser-smoke-token');
            localStorage.removeItem('mynd_chat_history_v1');
            localStorage.removeItem('mynd_active_chat_v1');
            """
        )

        response = page.goto(f'{base_url}/', wait_until='networkidle')

        assert response is not None and response.ok
        expect(page.locator('[data-auth-view="workspace"]')).to_be_visible()
        expect(page.locator('[data-auth-view="public"]')).to_have_count(0)
        new_chat_button = page.locator('.primary-nav .nav-item').first
        expect(new_chat_button).to_be_visible()
        expect(page.locator('.landing')).to_be_visible()
        initial_chat_count = page.locator('.history-item').count()

        new_chat_button.click()

        expect(page.locator('.history-item')).to_have_count(initial_chat_count + 1)
        expect(page.locator('.landing')).to_be_visible()
        assert page_errors == []
        browser.close()

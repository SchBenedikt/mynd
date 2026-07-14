"""Cloud Browser v2 – stealth Playwright automation, works with every website.

Anti-detection bypass, cookie consent handling, network interception,
iframe/shadow DOM support, mobile emulation, retry logic.
"""

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote_plus

from core.plugin_base import Plugin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global browser session (thread-local, lazy-init)
# ---------------------------------------------------------------------------

_browser_lock = threading.Lock()
_thread_local = threading.local()  # per-thread browser/context/pages
_screenshot_dir = Path(__file__).resolve().parents[2] / 'data' / 'browser_screenshots'
_download_dir = Path(__file__).resolve().parents[2] / 'data' / 'browser_downloads'
_blocking_enabled = True
_cookie_consent_enabled = True
_stealth_enabled = True

# Known cookie consent selectors (auto-dismiss)
COOKIE_SELECTORS = [
    'button[id*="accept"]', 'button[id*="consent"]', 'button[id*="agree"]',
    'button[class*="accept"]', 'button[class*="consent"]', 'button[class*="agree"]',
    'button[data-testid*="accept"]', 'button[data-testid*="consent"]',
    'a[id*="accept"]', 'a[class*="accept"]', 'a[class*="consent"]',
    '[role="button"][id*="accept"]', '[role="button"][class*="accept"]',
    '#onetrust-accept-btn-handler',
    '.qc-cmp2-summary-buttons button[mode="primary"]',
    'button.fc-cta-consent',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '.cc-accept', '.cc-allow', '.cc-btn.cc-allow',
    'button[title="Alle akzeptieren"]', 'button[title="Accept All"]',
    'button[title="Accept all"]', 'button[title="Accept"]',
    'button[title="Akzeptieren"]', 'button[title="Zustimmen"]',
    'button[title="Alle Cookies akzeptieren"]',
    'button:has-text("Alle akzeptieren")', 'button:has-text("Accept All")',
    'button:has-text("Accept all")', 'button:has-text("Accept cookies")',
    'button:has-text("Akzeptieren")', 'button:has-text("Zustimmen")',
    'button:has-text("OK")', 'button:has-text("Verstanden")',
    'button:has-text("Einverstanden")', 'button:has-text("Ich stimme zu")',
]

# Known ad/tracker domains to block
BLOCKED_DOMAINS = {
    'googleads.g.doubleclick.net', 'pagead2.googlesyndication.com',
    'adservice.google.com', 'www.googletagmanager.com',
    'connect.facebook.net', 'static.ads-twitter.com',
    'analytics.twitter.com', 'ads.linkedin.com',
    'bat.bing.com', 'ad.doubleclick.net',
    'www.google-analytics.com', 'ssl.google-analytics.com',
    'stats.wp.com', 'pixel.wp.com',
    'mc.yandex.ru', 'an.yandex.ru',
    'counter.yadro.ru', 'top-fwz1.mail.ru',
    'c.hit.gemius.pl', 'trackcmp.net',
    '热.com', 'plausible.io', 'analytics Bunny.net',
    'scripts.simpleanalyticscdn.com',
}


def _ensure_browser():
    """Lazily start Playwright + Chromium per thread."""
    tl = _thread_local
    if hasattr(tl, 'browser') and tl.browser and tl.browser.is_connected():
        return tl.browser
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run:\n"
            "  pip3 install playwright playwright-stealth\n"
            "  playwright install chromium"
        )
    tl.playwright = sync_playwright().start()
    tl.browser = tl.playwright.chromium.launch(
        headless=True,
        args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-infobars',
            '--window-size=1920,1080',
        ]
    )
    tl.context = tl.browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="de-DE",
        timezone_id="Europe/Berlin",
        permissions=["geolocation"],
        geolocation={"latitude": 52.52, "longitude": 13.405},
        color_scheme="light",
        has_touch=False,
        java_script_enabled=True,
        bypass_csp=False,
        extra_http_headers={
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        },
    )
    tl.context.set_default_timeout(15000)
    tl.context.set_default_navigation_timeout(30000)
    tl.pages = {}
    tl.active_tab = None
    _screenshot_dir.mkdir(parents=True, exist_ok=True)
    _download_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Playwright browser started (thread=%s, stealth=%s)",
                threading.current_thread().name, _stealth_enabled)
    return tl.browser


def _apply_stealth(page):
    """Apply stealth patches to a page to avoid bot detection."""
    if not _stealth_enabled:
        return
    try:
        from playwright_stealth import Stealth
        s = Stealth()
        s.apply(page)
    except ImportError:
        pass
    except Exception:
        pass
    # Additional manual stealth patches
    try:
        page.evaluate("""() => {
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            // Override chrome runtime
            window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(params);
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['de-DE', 'de', 'en-US', 'en']
            });
        }""")
    except Exception:
        pass


def _setup_blocking(page):
    """Set up network request blocking for ads/trackers."""
    if not _blocking_enabled:
        return
    try:
        page.route("**/*", lambda route: (
            route.abort()
            if any(d in route.request.url for d in BLOCKED_DOMAINS)
            else route.continue_()
        ))
    except Exception:
        pass


def _dismiss_cookie_consent(page):
    """Try to automatically dismiss cookie consent banners."""
    if not _cookie_consent_enabled:
        return False

    for sel in COOKIE_SELECTORS:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=1000):
                btn.click(timeout=2000)
                page.wait_for_timeout(500)
                logger.info("Dismissed cookie consent: %s", sel)
                return True
        except Exception:
            continue
    return False


# Module-level aliases for test compatibility (delegate to thread-local)
def _pages():
    return getattr(_thread_local, 'pages', {})

def _active_tab():
    return getattr(_thread_local, 'active_tab', None)


def _close_browser():
    """Shut down Playwright for the current thread."""
    tl = _thread_local
    for p in getattr(tl, 'pages', {}).values():
        try:
            p.close()
        except Exception:
            pass
    tl.pages = {}
    tl.active_tab = None
    if hasattr(tl, 'context') and tl.context:
        try:
            tl.context.close()
        except Exception:
            pass
    if hasattr(tl, 'browser') and tl.browser:
        try:
            tl.browser.close()
        except Exception:
            pass
    if hasattr(tl, 'playwright') and tl.playwright:
        try:
            tl.playwright.stop()
        except Exception:
            pass
    tl.playwright = tl.browser = tl.context = None
    logger.info("Playwright browser stopped (thread=%s)", threading.current_thread().name)


def _save_screenshot(page, name="page"):
    """Take screenshot, save to disk, return relative path."""
    _screenshot_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    fname = f"{name}_{ts}.png"
    fpath = _screenshot_dir / fname
    page.screenshot(path=str(fpath), full_page=False)
    return f"data/browser_screenshots/{fname}"


def _safe_url(url):
    """Validate and normalize URL."""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def _page_to_dict(page):
    """Extract structured info from a page."""
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    try:
        url = page.url or ""
    except Exception:
        url = ""
    try:
        text = page.inner_text("body")[:12000]
    except Exception:
        text = ""
    try:
        meta = page.evaluate("""() => {
            const m = {};
            document.querySelectorAll('meta').forEach(el => {
                const name = el.getAttribute('name') || el.getAttribute('property') || '';
                const content = el.getAttribute('content') || '';
                if (name && content) m[name] = content;
            });
            return m;
        }""")
    except Exception:
        meta = {}
    return {"title": title, "url": url, "text": text, "meta": meta}


def _smart_wait(page, wait="auto"):
    """Smart wait: wait for page to be reasonably loaded."""
    if wait == "load":
        page.wait_for_load_state("load", timeout=15000)
    elif wait == "networkidle":
        page.wait_for_load_state("networkidle", timeout=20000)
    elif wait == "domcontentloaded":
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    elif wait == "auto":
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
    # Dismiss cookie consent after load
    try:
        _dismiss_cookie_consent(page)
    except Exception:
        pass


def _retry(fn, retries=2, delay=0.5):
    """Simple retry wrapper."""
    last_err = None
    for i in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < retries:
                time.sleep(delay)
    raise last_err


def _find_in_iframes(page, selector):
    """Find an element across main page and all iframes."""
    # Try main page first
    try:
        loc = page.locator(selector).first
        if loc.is_visible(timeout=500):
            return loc
    except Exception:
        pass
    # Try iframes
    try:
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                loc = frame.locator(selector).first
                if loc.is_visible(timeout=500):
                    return loc
            except Exception:
                continue
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def browser_open(url: str, wait: str = "auto", dismiss_cookies: bool = True) -> str:
    """Open a URL in the cloud browser. Anti-detection stealth enabled."""
    with _browser_lock:
        url = _safe_url(url)
        page = _get_page()
        try:
            _apply_stealth(page)
            _setup_blocking(page)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            _smart_wait(page, wait)
            if dismiss_cookies:
                _dismiss_cookie_consent(page)
            info = _page_to_dict(page)
            screenshot = _save_screenshot(page, "open")
            return json.dumps({
                "success": True,
                "screenshot": screenshot,
                "screenshot_available": True,
                "title": info["title"],
                "url": info["url"],
                "text_preview": info["text"][:3000],
                "meta": info["meta"],
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e), "url": url})


def _get_page(tab_id=None):
    """Return the requested or active page (thread-local)."""
    tl = _thread_local
    _ensure_browser()
    if not tl.pages:
        page = tl.context.new_page()
        tid = str(id(page))
        tl.pages[tid] = page
        tl.active_tab = tid
        _apply_stealth(page)
        _setup_blocking(page)
        return page
    if tab_id and tab_id in tl.pages:
        return tl.pages[tab_id]
    if tl.active_tab and tl.active_tab in tl.pages:
        return tl.pages[tl.active_tab]
    tid, page = next(iter(tl.pages.items()))
    tl.active_tab = tid
    return page


def browser_screenshot(full_page: bool = False, element: str = "") -> str:
    """Take a screenshot of the current page or a specific element."""
    with _browser_lock:
        page = _get_page()
        try:
            _screenshot_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time() * 1000)
            fname = f"screenshot_{ts}.png"
            fpath = _screenshot_dir / fname
            if element:
                loc = _find_in_iframes(page, element) or page.locator(element).first
                loc.screenshot(path=str(fpath))
            else:
                page.screenshot(path=str(fpath), full_page=full_page)
            return json.dumps({
                "success": True,
                "screenshot": f"data/browser_screenshots/{fname}",
                "url": page.url,
                "title": page.title(),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_extract(mode: str = "text") -> str:
    """Extract content from the current page.
    mode: 'text', 'links', 'images', 'structured', 'forms', 'tables',
          'code', 'meta', 'full', 'readability'
    """
    with _browser_lock:
        page = _get_page()
        try:
            if mode == "text":
                content = page.inner_text("body")[:20000]
                return json.dumps({"success": True, "text": content}, ensure_ascii=False)

            elif mode == "links":
                links = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                        text: (a.innerText || '').trim().slice(0, 200),
                        href: a.href,
                        title: a.title || '',
                        rel: a.rel || '',
                        target: a.target || ''
                    })).filter(l => l.href && l.text && !l.href.startsWith('javascript:'));
                }""")
                return json.dumps({"success": True, "links": links[:1000], "count": len(links)}, ensure_ascii=False)

            elif mode == "images":
                images = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('img[src]')).map(img => ({
                        src: img.src,
                        alt: img.alt || '',
                        title: img.title || '',
                        width: img.naturalWidth,
                        height: img.naturalHeight,
                        loading: img.loading || '',
                        parent_tag: img.parentElement?.tagName || ''
                    })).filter(i => i.src && i.width > 10);
                }""")
                return json.dumps({"success": True, "images": images[:500], "count": len(images)}, ensure_ascii=False)

            elif mode == "structured":
                data = page.evaluate("""() => {
                    const result = [];
                    const walk = (node, depth) => {
                        if (depth > 8) return;
                        for (const child of node.children) {
                            const tag = child.tagName.toLowerCase();
                            if (/^h[1-6]$/.test(tag)) {
                                result.push({type: 'heading', level: parseInt(tag[1]),
                                    text: child.innerText.trim().slice(0, 500)});
                            } else if (tag === 'p') {
                                const text = child.innerText.trim();
                                if (text.length > 10) result.push({type: 'paragraph', text: text.slice(0, 3000)});
                            } else if (tag === 'ul' || tag === 'ol') {
                                const items = Array.from(child.querySelectorAll(':scope > li'))
                                    .map(li => li.innerText.trim().slice(0, 500))
                                    .filter(t => t.length > 0);
                                if (items.length) result.push({type: tag, items: items.slice(0, 100)});
                            } else if (tag === 'table') {
                                const rows = Array.from(child.querySelectorAll('tr')).slice(0, 100)
                                    .map(tr => Array.from(tr.querySelectorAll('td,th'))
                                        .map(c => c.innerText.trim().slice(0, 300)));
                                if (rows.length) result.push({type: 'table', rows});
                            } else if (tag === 'pre' || tag === 'code') {
                                result.push({type: 'code', text: child.innerText.trim().slice(0, 5000)});
                            } else if (tag === 'blockquote') {
                                result.push({type: 'quote', text: child.innerText.trim().slice(0, 1000)});
                            } else if (tag === 'details') {
                                const summary = child.querySelector('summary');
                                const content = child.innerText.trim().slice(0, 1000);
                                result.push({type: 'details', summary: summary?.innerText || '', content});
                            } else if (tag === 'dl') {
                                const items = [];
                                for (const dt of child.querySelectorAll('dt')) {
                                    const dd = dt.nextElementSibling;
                                    items.push({term: dt.innerText.trim(), definition: dd?.innerText?.trim() || ''});
                                }
                                if (items.length) result.push({type: 'definition_list', items});
                            }
                            walk(child, depth + 1);
                        }
                    };
                    walk(document.body, 0);
                    return result;
                }""")
                return json.dumps({"success": True, "structured": data[:2000], "count": len(data)}, ensure_ascii=False)

            elif mode == "forms":
                forms = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('form')).map((f, i) => ({
                        action: f.action || '',
                        method: f.method || 'GET',
                        id: f.id || '',
                        name: f.name || '',
                        fields: Array.from(f.querySelectorAll('input,textarea,select,button')).map(el => ({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || '',
                            name: el.name || '',
                            placeholder: el.placeholder || '',
                            value: el.value || '',
                            id: el.id || '',
                            required: el.required,
                            disabled: el.disabled,
                            autocomplete: el.autocomplete || '',
                            pattern: el.pattern || '',
                            options: el.tagName === 'SELECT'
                                ? Array.from(el.options).map(o => ({value: o.value, text: o.text, selected: o.selected}))
                                : undefined
                        }))
                    }));
                }""")
                return json.dumps({"success": True, "forms": forms}, ensure_ascii=False)

            elif mode == "tables":
                tables = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('table')).map((t, i) => {
                        const headers = Array.from(t.querySelectorAll('thead th, tr:first-child th'))
                            .map(th => th.innerText.trim().slice(0, 200));
                        const rows = Array.from(t.querySelectorAll('tbody tr, tr:not(:first-child)')).slice(0, 200)
                            .map(tr => Array.from(tr.querySelectorAll('td'))
                                .map(td => td.innerText.trim().slice(0, 300)));
                        return {index: i, headers, rows, rowCount: rows.length,
                                caption: t.caption?.innerText || ''};
                    });
                }""")
                return json.dumps({"success": True, "tables": tables}, ensure_ascii=False)

            elif mode == "code":
                code_blocks = page.evaluate("""() => {
                    const blocks = [];
                    document.querySelectorAll('pre code, pre, .highlight, .code-block, [class*="code"]').forEach(el => {
                        const text = el.innerText.trim();
                        if (text.length > 10) {
                            blocks.push({
                                text: text.slice(0, 5000),
                                language: el.className.match(/lang(?:uage)?-([\\w-]+)/)?.[1] || '',
                                parent: el.parentElement?.className || ''
                            });
                        }
                    });
                    return blocks;
                }""")
                return json.dumps({"success": True, "code_blocks": code_blocks[:50]}, ensure_ascii=False)

            elif mode == "meta":
                meta = page.evaluate("""() => {
                    const result = {
                        title: document.title,
                        description: '',
                        keywords: '',
                        og: {},
                        twitter: {},
                        json_ld: [],
                        canonical: '',
                        robots: '',
                        viewport: ''
                    };
                    document.querySelectorAll('meta').forEach(el => {
                        const name = (el.getAttribute('name') || el.getAttribute('property') || '').toLowerCase();
                        const content = el.getAttribute('content') || '';
                        if (name === 'description') result.description = content;
                        else if (name === 'keywords') result.keywords = content;
                        else if (name === 'robots') result.robots = content;
                        else if (name === 'viewport') result.viewport = content;
                        else if (name.startsWith('og:')) result.og[name.slice(3)] = content;
                        else if (name.startsWith('twitter:')) result.twitter[name.slice(8)] = content;
                    });
                    const canonical = document.querySelector('link[rel="canonical"]');
                    if (canonical) result.canonical = canonical.href;
                    document.querySelectorAll('script[type="application/ld+json"]').forEach(el => {
                        try { result.json_ld.push(JSON.parse(el.textContent)); } catch {}
                    });
                    return result;
                }""")
                return json.dumps({"success": True, "meta": meta}, ensure_ascii=False)

            elif mode == "readability":
                # Extract main content using readability-like heuristics
                data = page.evaluate("""() => {
                    // Remove noise elements
                    const removeSelectors = 'nav, header, footer, aside, .sidebar, .ad, .ads, .social, .share, .related, .comments, .newsletter, .popup, .modal, [role="navigation"], [role="banner"], [role="contentinfo"]';
                    const clone = document.body.cloneNode(true);
                    clone.querySelectorAll(removeSelectors).forEach(el => el.remove());

                    // Find article/main content
                    const article = clone.querySelector('article, main, [role="main"], .content, .post, .entry, .article');
                    const content = article || clone;

                    // Extract text with structure
                    const result = [];
                    const walker = (node) => {
                        if (node.nodeType === 3) {
                            const text = node.textContent.trim();
                            if (text.length > 5) result.push(text);
                        } else if (node.nodeType === 1) {
                            const tag = node.tagName.toLowerCase();
                            if (tag === 'br') result.push('\\n');
                            else if (/^h[1-6]$/.test(tag)) result.push('\\n\\n## ' + node.innerText.trim() + '\\n');
                            else if (tag === 'p') result.push('\\n\\n' + node.innerText.trim());
                            else if (tag === 'li') result.push('\\n- ' + node.innerText.trim());
                            else if (tag === 'blockquote') result.push('\\n> ' + node.innerText.trim());
                            for (const child of node.childNodes) walker(child);
                        }
                    };
                    for (const child of content.childNodes) walker(child);

                    return {
                        text: result.join('').replace(/\\n{3,}/g, '\\n\\n').trim().slice(0, 20000),
                        title: document.title,
                        url: window.location.href
                    };
                }""")
                return json.dumps({"success": True, **data}, ensure_ascii=False)

            elif mode == "full":
                info = _page_to_dict(page)
                links = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('a[href]')).slice(0, 500).map(a => ({
                        text: (a.innerText || '').trim().slice(0, 200), href: a.href
                    })).filter(l => l.href && l.text);
                }""")
                images = page.evaluate("""() => {
                    return Array.from(document.querySelectorAll('img[src]')).slice(0, 100).map(img => ({
                        src: img.src, alt: img.alt || ''
                    })).filter(i => i.src);
                }""")
                return json.dumps({
                    "success": True,
                    "title": info["title"],
                    "url": info["url"],
                    "text": info["text"][:15000],
                    "meta": info["meta"],
                    "links": links,
                    "images": images,
                }, ensure_ascii=False)

            else:
                return json.dumps({"success": False, "error": f"Unknown mode: {mode}. Use: text, links, images, structured, forms, tables, code, meta, readability, full"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_click(selector: str, wait_after: float = 1.0, iframe: bool = False) -> str:
    """Click an element on the page by CSS selector. Supports iframes."""
    with _browser_lock:
        page = _get_page()
        try:
            if iframe:
                loc = _find_in_iframes(page, selector)
                if not loc:
                    return json.dumps({"success": False, "error": f"Element not found in any frame: {selector}"})
            else:
                loc = page.locator(selector).first
            loc.click(timeout=10000)
            _smart_wait(page, "auto")
            time.sleep(wait_after)
            info = _page_to_dict(page)
            screenshot = _save_screenshot(page, "click")
            return json.dumps({
                "success": True,
                "screenshot": screenshot,
                "screenshot_available": True,
                "clicked": selector,
                "new_url": info["url"],
                "new_title": info["title"],
                "text_preview": info["text"][:2000],
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e), "selector": selector})


def browser_type(selector: str, text: str, press_enter: bool = False,
                 clear: bool = True, delay: int = 30, iframe: bool = False) -> str:
    """Type text into an input field. Supports iframes."""
    with _browser_lock:
        page = _get_page()
        try:
            if iframe:
                loc = _find_in_iframes(page, selector)
                if not loc:
                    return json.dumps({"success": False, "error": f"Input not found in any frame: {selector}"})
            else:
                loc = page.locator(selector).first
            loc.click(timeout=5000)
            if clear:
                loc.fill("")
            loc.type(text, delay=delay)
            if press_enter:
                loc.press("Enter")
                _smart_wait(page, "auto")
            info = _page_to_dict(page)
            return json.dumps({
                "success": True,
                "typed": text,
                "selector": selector,
                "enter_pressed": press_enter,
                "url": info["url"],
                "title": info["title"],
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_evaluate(expression: str) -> str:
    """Execute JavaScript in the page context and return the result."""
    with _browser_lock:
        page = _get_page()
        try:
            result = page.evaluate(expression)
            if isinstance(result, (dict, list)):
                result_str = json.dumps(result, ensure_ascii=False, default=str)[:15000]
            else:
                result_str = str(result)[:15000]
            return json.dumps({"success": True, "result": result_str}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_navigate(url: str) -> str:
    """Navigate to a URL (same as browser_open)."""
    return browser_open(url)


def browser_back() -> str:
    """Go back in browser history."""
    with _browser_lock:
        page = _get_page()
        try:
            page.go_back(timeout=15000)
            _smart_wait(page, "auto")
            info = _page_to_dict(page)
            screenshot = _save_screenshot(page, "back")
            return json.dumps({
                "success": True, "screenshot": screenshot, "screenshot_available": True,
                "url": info["url"], "title": info["title"],
                "text_preview": info["text"][:2000],
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_forward() -> str:
    """Go forward in browser history."""
    with _browser_lock:
        page = _get_page()
        try:
            page.go_forward(timeout=15000)
            _smart_wait(page, "auto")
            info = _page_to_dict(page)
            screenshot = _save_screenshot(page, "forward")
            return json.dumps({
                "success": True, "screenshot": screenshot, "screenshot_available": True,
                "url": info["url"], "title": info["title"],
                "text_preview": info["text"][:2000],
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_scroll(direction: str = "down", amount: int = 500) -> str:
    """Scroll the page up or down by a pixel amount."""
    with _browser_lock:
        page = _get_page()
        try:
            delta = amount if direction == "down" else -amount
            page.evaluate(f"window.scrollBy(0, {delta})")
            time.sleep(0.5)
            pos = page.evaluate("JSON.stringify({x: window.scrollX, y: window.scrollY, max: document.body.scrollHeight - window.innerHeight})")
            return json.dumps({
                "success": True, "scrolled": direction, "amount": delta,
                "position": json.loads(pos),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_select(selector: str, value: str) -> str:
    """Select an option in a <select> dropdown."""
    with _browser_lock:
        page = _get_page()
        try:
            page.select_option(selector, value, timeout=5000)
            return json.dumps({"success": True, "selector": selector, "selected": value})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_hover(selector: str) -> str:
    """Hover over an element (triggers hover menus, tooltips)."""
    with _browser_lock:
        page = _get_page()
        try:
            page.locator(selector).first.hover(timeout=5000)
            time.sleep(0.5)
            # Check for visible dropdowns/menus that appeared
            visible = page.evaluate("""() => {
                const menus = [];
                document.querySelectorAll('[class*="dropdown"], [class*="menu"], [role="menu"], [role="listbox"]').forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (style.display !== 'none' && style.visibility !== 'hidden') {
                        menus.push({tag: el.tagName, class: el.className.slice(0, 100), text: el.innerText.slice(0, 200)});
                    }
                });
                return menus;
            }""")
            return json.dumps({"success": True, "hovered": selector, "visible_menus": visible})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_wait_for(selector: str, timeout: float = 10.0, state: str = "visible") -> str:
    """Wait for an element to appear on the page. state: visible|attached|detached|hidden"""
    with _browser_lock:
        page = _get_page()
        try:
            page.wait_for_selector(selector, state=state, timeout=int(timeout * 1000))
            return json.dumps({"success": True, "found": selector, "state": state})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e), "selector": selector})


def browser_list_tabs() -> str:
    """List all open browser tabs."""
    with _browser_lock:
        tl = _thread_local
        _ensure_browser()
        tabs = []
        for tid, page in tl.pages.items():
            try:
                tabs.append({
                    "id": tid,
                    "url": page.url,
                    "title": page.title(),
                    "active": tid == tl.active_tab,
                })
            except Exception:
                tabs.append({"id": tid, "url": "unknown", "title": "unknown", "active": False})
        return json.dumps({"success": True, "tabs": tabs, "active_tab": tl.active_tab})


def browser_new_tab(url: str = "") -> str:
    """Open a new browser tab."""
    with _browser_lock:
        tl = _thread_local
        _ensure_browser()
        page = tl.context.new_page()
        tid = str(id(page))
        tl.pages[tid] = page
        tl.active_tab = tid
        _apply_stealth(page)
        _setup_blocking(page)
        if url:
            try:
                page.goto(_safe_url(url), wait_until="domcontentloaded", timeout=30000)
                _smart_wait(page, "auto")
            except Exception as e:
                return json.dumps({"success": True, "tab_id": tid, "warning": str(e)})
        info = _page_to_dict(page)
        return json.dumps({
            "success": True, "tab_id": tid, "url": info["url"], "title": info["title"],
        })


def browser_switch_tab(tab_id: str) -> str:
    """Switch to a different tab."""
    with _browser_lock:
        tl = _thread_local
        if tab_id not in tl.pages:
            return json.dumps({"success": False, "error": f"Tab {tab_id} not found"})
        tl.active_tab = tab_id
        page = tl.pages[tab_id]
        info = _page_to_dict(page)
        return json.dumps({
            "success": True, "tab_id": tab_id, "url": info["url"], "title": info["title"],
        })


def browser_close_tab(tab_id: str = "") -> str:
    """Close a tab (or the active tab)."""
    with _browser_lock:
        tl = _thread_local
        tid = tab_id or tl.active_tab
        if tid not in tl.pages:
            return json.dumps({"success": False, "error": f"Tab {tid} not found"})
        page = tl.pages.pop(tid)
        try:
            page.close()
        except Exception:
            pass
        if tid == tl.active_tab:
            tl.active_tab = next(iter(tl.pages), None)
        return json.dumps({"success": True, "closed_tab": tid, "active_tab": tl.active_tab})


def browser_search(query: str, engine: str = "duckduckgo") -> str:
    """Search the web using a real browser. Uses DuckDuckGo (best anti-bot tolerance)."""
    with _browser_lock:
        page = _get_page()
        try:
            _apply_stealth(page)
            if engine == "google":
                search_url = f"https://www.google.com/search?q={quote_plus(query)}&hl=de"
            elif engine == "duckduckgo":
                search_url = f"https://duckduckgo.com/?q={quote_plus(query)}&kl=de-de"
            elif engine == "bing":
                search_url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=de"
            else:
                search_url = f"https://duckduckgo.com/?q={quote_plus(query)}"
            page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            _smart_wait(page, "auto")
            time.sleep(2)

            # DuckDuckGo extraction (most reliable)
            results = page.evaluate("""() => {
                const results = [];
                // DuckDuckGo organic results
                document.querySelectorAll('article[data-testid="result"], article[data-testid="ad"]').forEach(el => {
                    const text = el.innerText.trim();
                    const lines = text.split('\\n').filter(l => l.trim());
                    const linkEl = el.querySelector('a[href]');
                    const url = linkEl?.href || '';
                    if (url && !url.includes('duckduckgo.com') && lines.length >= 2) {
                        // First line is usually the title, second is URL, rest is snippet
                        results.push({
                            title: lines[0].slice(0, 200),
                            url: url,
                            snippet: lines.slice(2).join(' ').trim().slice(0, 400) || lines[1] || ''
                        });
                    }
                });
                // Fallback: look for any links with h2/h3 parents
                if (!results.length) {
                    document.querySelectorAll('h2 a[href], h3 a[href]').forEach(a => {
                        if (!a.href.includes('duckduckgo.com')) {
                            const snippet = a.closest('div,li,section')?.innerText?.trim().slice(0, 400) || '';
                            results.push({
                                title: a.innerText.trim().slice(0, 200),
                                url: a.href,
                                snippet
                            });
                        }
                    });
                }
                // Google organic results
                if (!results.length) {
                    document.querySelectorAll('div.g, div[data-sokoban-container]').forEach(el => {
                        const titleEl = el.querySelector('h3');
                        const linkEl = el.querySelector('a[href]');
                        const snippetEl = el.querySelector('[data-sncf], .VwiC3b, .IsZvec, span.aCOpRe');
                        if (titleEl && linkEl && !linkEl.href.includes('google.com')) {
                            results.push({
                                title: titleEl.innerText.trim().slice(0, 200),
                                url: linkEl.href,
                                snippet: (snippetEl ? snippetEl.innerText : '').trim().slice(0, 400)
                            });
                        }
                    });
                }
                // Bing results
                if (!results.length) {
                    document.querySelectorAll('.b_algo').forEach(el => {
                        const titleEl = el.querySelector('h2 a');
                        const snippetEl = el.querySelector('.b_caption p, .b_lineclamp2');
                        if (titleEl) {
                            results.push({
                                title: titleEl.innerText.trim().slice(0, 200),
                                url: titleEl.href,
                                snippet: (snippetEl ? snippetEl.innerText : '').trim().slice(0, 400)
                            });
                        }
                    });
                }
                return results.slice(0, 15);
            }""")
            screenshot = _save_screenshot(page, "search")
            return json.dumps({
                "success": True, "screenshot": screenshot, "screenshot_available": True,
                "query": query, "engine": engine,
                "results": results, "result_count": len(results),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_fill_form(form_selector: str, fields: str) -> str:
    """Fill multiple fields in a form at once. fields is a JSON string of {selector: value} pairs."""
    with _browser_lock:
        page = _get_page()
        try:
            field_map = json.loads(fields) if isinstance(fields, str) else fields
            filled = []
            errors = []
            for sel, val in field_map.items():
                try:
                    loc = _find_in_iframes(page, sel) or page.locator(sel).first
                    loc.fill(str(val))
                    filled.append(sel)
                except Exception as e:
                    errors.append(f"{sel}: {str(e)[:100]}")
            return json.dumps({
                "success": len(filled) > 0,
                "filled": filled,
                "errors": errors,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_pdf() -> str:
    """Save the current page as a PDF file."""
    with _browser_lock:
        page = _get_page()
        try:
            _screenshot_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time() * 1000)
            fname = f"page_{ts}.pdf"
            fpath = _screenshot_dir / fname
            page.pdf(path=str(fpath), format="A4", print_background=True,
                     margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"})
            return json.dumps({
                "success": True,
                "pdf": f"data/browser_screenshots/{fname}",
                "url": page.url,
                "title": page.title(),
            })
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_cookies(action: str = "get", name: str = "", value: str = "",
                    url: str = "", domain: str = "") -> str:
    """Get/set/delete cookies. action: get|set|delete|clear"""
    with _browser_lock:
        tl = _thread_local
        _ensure_browser()
        try:
            if action == "get":
                cookies = tl.context.cookies()
                if domain:
                    cookies = [c for c in cookies if domain in c.get("domain", "")]
                if name:
                    cookies = [c for c in cookies if c.get("name") == name]
                return json.dumps({"success": True, "cookies": cookies[:200], "count": len(cookies)}, ensure_ascii=False)
            elif action == "set":
                cookie = {"name": name, "value": value, "domain": domain or None, "path": "/"}
                if url:
                    cookie["url"] = url
                tl.context.add_cookies([cookie])
                return json.dumps({"success": True, "set": name})
            elif action == "delete":
                if name:
                    tl.context.clear_cookies(name=name)
                else:
                    tl.context.clear_cookies()
                return json.dumps({"success": True, "deleted": name or "all"})
            elif action == "clear":
                tl.context.clear_cookies()
                return json.dumps({"success": True, "cleared": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_set_viewport(width: int = 1280, height: int = 900) -> str:
    """Set the browser viewport size."""
    with _browser_lock:
        page = _get_page()
        try:
            page.set_viewport_size({"width": width, "height": height})
            return json.dumps({"success": True, "viewport": {"width": width, "height": height}})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_get_performance() -> str:
    """Get page performance metrics."""
    with _browser_lock:
        page = _get_page()
        try:
            metrics = page.evaluate("""() => {
                const perf = performance;
                const nav = perf.getEntriesByType('navigation')[0] || {};
                const resources = perf.getEntriesByType('resource');
                return {
                    domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
                    loadComplete: Math.round(nav.loadEventEnd || 0),
                    domInteractive: Math.round(nav.domInteractive || 0),
                    responseTime: Math.round(nav.responseEnd - nav.requestStart || 0),
                    resourceCount: resources.length,
                    totalTransferSize: resources.reduce((s, r) => s + (r.transferSize || 0), 0),
                    largestContentfulPaint: 0,
                    firstInputDelay: 0,
                    cumulativeLayoutShift: 0,
                };
            }""")
            # Try to get Core Web Vitals
            try:
                vitals = page.evaluate("""() => new Promise(resolve => {
                    const results = {};
                    try {
                        new PerformanceObserver(list => {
                            const entries = list.getEntries();
                            results.lcp = Math.round(entries[entries.length - 1]?.startTime || 0);
                        }).observe({type: 'largest-contentful-paint', buffered: true});
                    } catch {}
                    setTimeout(() => resolve(results), 1000);
                })""")
                metrics.update(vitals)
            except Exception:
                pass
            return json.dumps({"success": True, "metrics": metrics})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_network_log(action: str = "start", filter: str = "") -> str:
    """Log network requests. action: start|stop|get"""
    with _browser_lock:
        page = _get_page()
        try:
            if action == "start":
                page._network_log = []
                def on_request(request):
                    page._network_log.append({
                        "url": request.url[:200],
                        "method": request.method,
                        "resource_type": request.resource_type,
                        "timestamp": time.time(),
                    })
                page.on("request", on_request)
                return json.dumps({"success": True, "recording": True})
            elif action == "get":
                log = getattr(page, '_network_log', [])
                if filter:
                    log = [e for e in log if filter.lower() in e.get("url", "").lower()]
                return json.dumps({"success": True, "entries": log[-100:], "count": len(log)})
            elif action == "stop":
                page._network_log = []
                return json.dumps({"success": True, "recording": False})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_mobile_emulate(device: str = "iphone") -> str:
    """Switch to mobile viewport and user agent. device: iphone|ipad|pixel|galaxy"""
    devices = {
        "iphone": {"width": 390, "height": 844, "ua": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"},
        "ipad": {"width": 1024, "height": 1366, "ua": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"},
        "pixel": {"width": 412, "height": 915, "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"},
        "galaxy": {"width": 412, "height": 915, "ua": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"},
    }
    if device not in devices:
        return json.dumps({"success": False, "error": f"Unknown device: {device}. Use: {', '.join(devices.keys())}"})
    with _browser_lock:
        page = _get_page()
        try:
            d = devices[device]
            page.set_viewport_size({"width": d["width"], "height": d["height"]})
            page.evaluate(f"""() => {{
                Object.defineProperty(navigator, 'userAgent', {{ get: () => '{d["ua"]}' }});
                Object.defineProperty(navigator, 'platform', {{ get: () => 'iPhone' }});
            }}""")
            return json.dumps({"success": True, "device": device, "viewport": {"width": d["width"], "height": d["height"]}})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_get_shadow_dom(selector: str) -> str:
    """Extract content from Shadow DOM elements."""
    with _browser_lock:
        page = _get_page()
        try:
            result = page.evaluate("""(sel) => {
                const el = document.querySelector(sel);
                if (!el || !el.shadowRoot) return {error: 'No shadow root found'};
                return {
                    html: el.shadowRoot.innerHTML.slice(0, 10000),
                    text: el.shadowRoot.innerText?.slice(0, 5000) || '',
                    childCount: el.shadowRoot.children.length
                };
            }""", selector)
            return json.dumps({"success": True, **result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_intercept(enable: bool = True, block_domains: str = "",
                      mock_responses: str = "") -> str:
    """Enable/disable network interception. block_domains: comma-separated domains to block.
    mock_responses: JSON string of {url_pattern: response_body} for mocking."""
    with _browser_lock:
        page = _get_page()
        try:
            # Remove existing routes
            page.unroute_all()
            if not enable:
                return json.dumps({"success": True, "interception": "disabled"})
            # Block specified domains
            if block_domains:
                domains = [d.strip() for d in block_domains.split(",")]
                def block_handler(route):
                    if any(d in route.request.url for d in domains):
                        route.abort()
                    else:
                        route.continue_()
                page.route("**/*", block_handler)
            # Mock responses
            if mock_responses:
                mocks = json.loads(mock_responses)
                for pattern, body in mocks.items():
                    def mock_handler(route, b=body):
                        route.fulfill(status=200, content_type="application/json",
                                      body=json.dumps(b) if isinstance(b, (dict, list)) else str(b))
                    page.route(pattern, mock_handler)
            return json.dumps({"success": True, "interception": "enabled"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browser_dialog_handler(auto_accept: bool = True) -> str:
    """Configure how browser dialogs (alert, confirm, prompt) are handled."""
    with _browser_lock:
        page = _get_page()
        try:
            def handle_dialog(dialog):
                if auto_accept:
                    dialog.accept(dialog.default_value or "")
                else:
                    dialog.dismiss()
            page.on("dialog", handle_dialog)
            return json.dumps({"success": True, "auto_accept": auto_accept})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


def browserAccessibility_snapshot() -> str:
    """Get page structure snapshot via JS (accessibility API deprecated in newer Playwright)."""
    with _browser_lock:
        page = _get_page()
        try:
            snapshot = page.evaluate("""() => {
                const tree = {role: 'root', name: document.title, children: []};
                const walk = (node, parent, depth) => {
                    if (depth > 4) return;
                    const tag = node.tagName?.toLowerCase();
                    if (!tag) return;
                    const role = node.getAttribute('role') || tag;
                    const name = node.getAttribute('aria-label') || node.getAttribute('title') || '';
                    const child = {role, name: name.slice(0, 100), tag};
                    if (node.childNodes.length > 0 && node.childNodes.length < 20) {
                        child.children = [];
                        for (const c of node.childNodes) {
                            if (c.nodeType === 1) walk(c, child.children, depth + 1);
                        }
                    }
                    parent.push(child);
                };
                for (const child of document.body.children) {
                    walk(child, tree.children, 0);
                }
                return tree;
            }""")
            return json.dumps({"success": True, "snapshot": snapshot}, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})


# ---------------------------------------------------------------------------
# Plugin definition
# ---------------------------------------------------------------------------

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "Open a URL in the cloud browser with stealth anti-detection. Auto-dismisses cookie banners.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"},
                    "wait": {"type": "string", "enum": ["auto", "load", "networkidle", "domcontentloaded"], "default": "auto",
                             "description": "When to consider page loaded"},
                    "dismiss_cookies": {"type": "boolean", "default": True, "description": "Auto-dismiss cookie consent banners"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current page or a specific element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {"type": "boolean", "default": False},
                    "element": {"type": "string", "description": "CSS selector of element to screenshot"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_extract",
            "description": "Extract content from the current page. Modes: text, links, images, structured, forms, tables, code, meta, readability, full.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["text", "links", "images", "structured", "forms", "tables", "code", "meta", "readability", "full"],
                        "default": "text",
                        "description": "text=visible text, links=all links, structured=headings/paragraphs/tables/lists, forms=form fields, tables=HTML tables, code=code blocks, meta=SEO meta, readability=article content, full=all combined"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element on the page by CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector (e.g. 'button.submit', '#login')"},
                    "wait_after": {"type": "number", "default": 1.0},
                    "iframe": {"type": "boolean", "default": False, "description": "Search in iframes too"}
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Type text into an input field.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of input"},
                    "text": {"type": "string", "description": "Text to type"},
                    "press_enter": {"type": "boolean", "default": False},
                    "clear": {"type": "boolean", "default": True},
                    "delay": {"type": "integer", "default": 30, "description": "ms between keystrokes"},
                    "iframe": {"type": "boolean", "default": False}
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_evaluate",
            "description": "Execute JavaScript in the page context and return the result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "JavaScript expression to evaluate"}
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_search",
            "description": "Search the web using a real browser (DuckDuckGo recommended, best anti-bot tolerance).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "engine": {"type": "string", "enum": ["duckduckgo", "google", "bing"], "default": "duckduckgo"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate to a URL (same as browser_open).",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"]
            }
        }
    },
    {"type": "function", "function": {"name": "browser_back", "description": "Go back.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "browser_forward", "description": "Go forward.", "parameters": {"type": "object", "properties": {}}}},
    {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "Scroll the page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                    "amount": {"type": "integer", "default": 500}
                }
            }
        }
    },
    {"type": "function", "function": {"name": "browser_select", "description": "Select dropdown option.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "value": {"type": "string"}}, "required": ["selector", "value"]}}},
    {"type": "function", "function": {"name": "browser_hover", "description": "Hover over element.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}}},
    {"type": "function", "function": {"name": "browser_wait_for", "description": "Wait for element.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}, "timeout": {"type": "number", "default": 10}, "state": {"type": "string", "enum": ["visible", "attached", "detached", "hidden"], "default": "visible"}}, "required": ["selector"]}}},
    {"type": "function", "function": {"name": "browser_list_tabs", "description": "List tabs.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "browser_new_tab", "description": "Open new tab.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "browser_switch_tab", "description": "Switch tab.", "parameters": {"type": "object", "properties": {"tab_id": {"type": "string"}}, "required": ["tab_id"]}}},
    {"type": "function", "function": {"name": "browser_close_tab", "description": "Close tab.", "parameters": {"type": "object", "properties": {"tab_id": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "browser_fill_form", "description": "Fill multiple form fields at once.", "parameters": {"type": "object", "properties": {"form_selector": {"type": "string"}, "fields": {"type": "string", "description": "JSON: {\"#email\": \"val\"}"}}, "required": ["fields"]}}},
    {"type": "function", "function": {"name": "browser_pdf", "description": "Save page as PDF.", "parameters": {"type": "object", "properties": {}}}},
    {
        "type": "function",
        "function": {
            "name": "browser_cookies",
            "description": "Manage cookies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["get", "set", "delete", "clear"], "default": "get"},
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                    "domain": {"type": "string"},
                    "url": {"type": "string"}
                }
            }
        }
    },
    {"type": "function", "function": {"name": "browser_set_viewport", "description": "Resize viewport.", "parameters": {"type": "object", "properties": {"width": {"type": "integer", "default": 1280}, "height": {"type": "integer", "default": 900}}}}},
    {"type": "function", "function": {"name": "browser_get_performance", "description": "Page performance metrics + Core Web Vitals.", "parameters": {"type": "object", "properties": {}}}},
    {
        "type": "function",
        "function": {
            "name": "browser_network_log",
            "description": "Log network requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["start", "stop", "get"], "default": "get"},
                    "filter": {"type": "string", "description": "Filter by URL substring"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_mobile_emulate",
            "description": "Switch to mobile viewport + user agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {"type": "string", "enum": ["iphone", "ipad", "pixel", "galaxy"], "default": "iphone"}
                }
            }
        }
    },
    {"type": "function", "function": {"name": "browser_get_shadow_dom", "description": "Extract Shadow DOM content.", "parameters": {"type": "object", "properties": {"selector": {"type": "string"}}, "required": ["selector"]}}},
    {
        "type": "function",
        "function": {
            "name": "browser_intercept",
            "description": "Configure network interception (block domains, mock responses).",
            "parameters": {
                "type": "object",
                "properties": {
                    "enable": {"type": "boolean", "default": True},
                    "block_domains": {"type": "string", "description": "Comma-separated domains to block"},
                    "mock_responses": {"type": "string", "description": "JSON: {\"url_pattern\": response}"}
                }
            }
        }
    },
    {"type": "function", "function": {"name": "browser_dialog_handler", "description": "Auto-accept/dismiss JS dialogs.", "parameters": {"type": "object", "properties": {"auto_accept": {"type": "boolean", "default": True}}}}},
    {"type": "function", "function": {"name": "browser_accessibility_snapshot", "description": "Get accessibility tree of page.", "parameters": {"type": "object", "properties": {}}}},
]

_TOOL_MAP = {
    "browser_open": browser_open,
    "browser_screenshot": browser_screenshot,
    "browser_extract": browser_extract,
    "browser_click": browser_click,
    "browser_type": browser_type,
    "browser_evaluate": browser_evaluate,
    "browser_search": browser_search,
    "browser_navigate": browser_navigate,
    "browser_back": browser_back,
    "browser_forward": browser_forward,
    "browser_scroll": browser_scroll,
    "browser_select": browser_select,
    "browser_hover": browser_hover,
    "browser_wait_for": browser_wait_for,
    "browser_list_tabs": browser_list_tabs,
    "browser_new_tab": browser_new_tab,
    "browser_switch_tab": browser_switch_tab,
    "browser_close_tab": browser_close_tab,
    "browser_fill_form": browser_fill_form,
    "browser_pdf": browser_pdf,
    "browser_cookies": browser_cookies,
    "browser_set_viewport": browser_set_viewport,
    "browser_get_performance": browser_get_performance,
    "browser_network_log": browser_network_log,
    "browser_mobile_emulate": browser_mobile_emulate,
    "browser_get_shadow_dom": browser_get_shadow_dom,
    "browser_intercept": browser_intercept,
    "browser_dialog_handler": browser_dialog_handler,
    "browser_accessibility_snapshot": browserAccessibility_snapshot,
}

PROMPT_EXTRA = """CLOUD BROWSER v2 (STEALTH MODE):
You have a real Chromium browser with anti-detection stealth. Use it to browse any website, research topics, fill forms, take screenshots, and extract data.

NAVIGATION:
  browser_open(url, wait?, dismiss_cookies?)  — open URL (auto-stealth + cookie dismiss)
  browser_navigate(url)                       — alias for open
  browser_back() / browser_forward()          — history navigation
  browser_scroll(direction?, amount?)         — scroll up/down

CONTENT EXTRACTION:
  browser_extract(mode?) — modes: text|links|images|structured|forms|tables|code|meta|readability|full
    - readability: extracts article content (removes nav/footer/ads)
    - structured: headings, paragraphs, lists, tables, code blocks, quotes
    - tables: all HTML tables with headers
    - code: code blocks with language detection
    - meta: SEO metadata, Open Graph, JSON-LD

INTERACTION:
  browser_click(selector, iframe?)             — click element
  browser_type(selector, text, press_enter?)   — type into input
  browser_fill_form(fields)                    — fill multiple fields (JSON map)
  browser_select(selector, value)              — select dropdown
  browser_hover(selector)                      — hover (trigger menus)

SEARCH:
  browser_search(query, engine?) — search web (default: duckduckgo, best anti-bot)

JAVASCRIPT:
  browser_evaluate(expression) — run JS in page context

ADVANCED:
  browser_new_tab(url?) / browser_switch_tab(id) / browser_close_tab(id?)
  browser_screenshot(full_page?, element?)
  browser_cookies(action?) — get|set|delete|clear
  browser_set_viewport(width, height)
  browser_get_performance() — Core Web Vitals
  browser_network_log(action?) — start|stop|get network requests
  browser_mobile_emulate(device?) — iphone|ipad|pixel|galaxy
  browser_get_shadow_dom(selector)
  browser_intercept(enable, block_domains?, mock_responses?)
  browser_dialog_handler(auto_accept?)
  browser_accessibility_snapshot()
  browser_pdf()

CSS selectors: 'button.submit', '#email', 'input[name="q"]', 'a[href="/about"]'
Tip: browser_search() first, then browser_open() for detailed content.
Use readability mode for article extraction. Use tables mode for data extraction.
"""


class BrowserPlugin(Plugin):
    name = "browser"
    description = "Cloud Browser v2 – stealth Chromium with anti-detection, cookie consent, network blocking"
    version = "2.0.0"
    tools = _TOOLS
    tool_map = _TOOL_MAP
    PROMPT_EXTRA = PROMPT_EXTRA

    def on_load(self):
        logger.info("Browser v2 plugin loaded (stealth=%s, blocking=%s)", _stealth_enabled, _blocking_enabled)

    def on_unload(self):
        _close_browser()
        logger.info("Browser v2 plugin unloaded")

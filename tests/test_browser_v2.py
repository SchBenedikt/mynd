"""Cloud Browser v2 – comprehensive real-world tests."""
import json
import sys

sys.path.insert(0, '.')

from data.plugins.browser import (
    _close_browser,
    browser_back,
    browser_close_tab,
    browser_cookies,
    browser_evaluate,
    browser_extract,
    browser_get_performance,
    browser_intercept,
    browser_list_tabs,
    browser_mobile_emulate,
    browser_network_log,
    browser_new_tab,
    browser_open,
    browser_pdf,
    browser_screenshot,
    browser_scroll,
    browser_search,
    browser_set_viewport,
    browser_type,
    browserAccessibility_snapshot,
)

print("=" * 70)
print("CLOUD BROWSER v2 – REAL-WORLD TESTS")
print("=" * 70)

errors = []
passed = []

def test(name, fn):
    try:
        result = fn()
        if isinstance(result, dict):
            ok = result.get("success", False)
        elif isinstance(result, str):
            r = json.loads(result)
            ok = r.get("success", False)
            result = r
        else:
            ok = bool(result)
        if ok:
            passed.append(name)
            print(f"  ✓ {name}")
        else:
            errors.append(f"{name}: {result.get('error', 'failed')}")
            print(f"  ✗ {name}: {result.get('error', 'failed')}")
        return result
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"  ✗ {name}: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════
print("\n1. STEALTH MODE – Google (most aggressive bot detection)")
# ═══════════════════════════════════════════════════════════════════════
r = test("Open Google with stealth", lambda: browser_open("https://www.google.com"))
if r:
    print(f"    Title: {r.get('title')}")
    print(f"    URL: {r.get('url')}")

r = test("Search Google via JS", lambda: browser_evaluate("""
    const input = document.querySelector('input[name="q"]');
    if (input) {
        input.value = 'Playwright automation';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        'typed';
    } else {
        'no input found';
    }
"""))
if r:
    print(f"    Result: {r.get('result')}")

# ═══════════════════════════════════════════════════════════════════════
print("\n2. CONTENT EXTRACTION – Hacker News (structured content)")
# ═══════════════════════════════════════════════════════════════════════
r = test("Open Hacker News", lambda: browser_open("https://news.ycombinator.com"))
if r:
    print(f"    Title: {r.get('title')}")

r = test("Extract links", lambda: browser_extract("links"))
if r:
    count = r.get("count", 0)
    print(f"    Links: {count}")
    for l in r.get("links", [])[:5]:
        print(f"      → {l['text'][:40]} | {l['href'][:50]}")

r = test("Extract structured", lambda: browser_extract("structured"))
if r:
    count = r.get("count", 0)
    print(f"    Elements: {count}")
    for s in r.get("structured", [])[:5]:
        t = s.get("type")
        if t == "heading":
            print(f"      H{s.get('level')}: {s.get('text', '')[:50]}")
        elif t == "paragraph":
            print(f"      P: {s.get('text', '')[:60]}...")

r = test("Extract tables", lambda: browser_extract("tables"))
if r:
    print(f"    Tables: {len(r.get('tables', []))}")

# ═══════════════════════════════════════════════════════════════════════
print("\n3. WEB SEARCH – DuckDuckGo (best anti-bot tolerance)")
# ═══════════════════════════════════════════════════════════════════════
r = test("Search DuckDuckGo", lambda: browser_search("Python programming language", "duckduckgo"))
if r:
    print(f"    Results: {r.get('result_count', 0)}")
    for item in r.get("results", [])[:5]:
        print(f"      → {item['title'][:50]}")
        print(f"        {item['url'][:60]}")
        if item.get("snippet"):
            print(f"        {item['snippet'][:80]}...")

# ═══════════════════════════════════════════════════════════════════════
print("\n4. READABILITY MODE – Wikipedia article")
# ═══════════════════════════════════════════════════════════════════════
r = test("Open Wikipedia Python article", lambda: browser_open("https://en.wikipedia.org/wiki/Python_(programming_language)"))
if r:
    print(f"    Title: {r.get('title')}")

r = test("Extract readability", lambda: browser_extract("readability"))
if r:
    text = r.get("text", "")
    print(f"    Article length: {len(text)} chars")
    print(f"    First 300 chars:\n      {text[:300]}...")

# ═══════════════════════════════════════════════════════════════════════
print("\n5. META EXTRACTION – SEO data")
# ═══════════════════════════════════════════════════════════════════════
r = test("Extract meta tags", lambda: browser_extract("meta"))
if r:
    meta = r.get("meta", {})
    print(f"    Title: {meta.get('title', '')[:60]}")
    print(f"    Description: {meta.get('description', '')[:80]}")
    print(f"    OG title: {meta.get('og', {}).get('title', '')[:60]}")
    print(f"    Canonical: {meta.get('canonical', '')[:60]}")
    print(f"    JSON-LD entries: {len(meta.get('json_ld', []))}")

# ═══════════════════════════════════════════════════════════════════════
print("\n6. FORM INTERACTION – Wikipedia search")
# ═══════════════════════════════════════════════════════════════════════
r = test("Open Wikipedia", lambda: browser_open("https://en.wikipedia.org"))
r = test("Type search", lambda: browser_type('input[name="search"]', 'Artificial Intelligence', press_enter=True))
if r:
    print(f"    Typed: {r.get('typed')}")
    print(f"    New title: {r.get('title')}")

# ═══════════════════════════════════════════════════════════════════════
print("\n7. NAVIGATION + SCROLL")
# ═══════════════════════════════════════════════════════════════════════
r = test("Go back", lambda: browser_back())
if r:
    print(f"    Back to: {r.get('title')}")

r = test("Scroll down 1000px", lambda: browser_scroll("down", 1000))
if r:
    print(f"    Position: {r.get('position')}")

r = test("Scroll up 500px", lambda: browser_scroll("up", 500))

# ═══════════════════════════════════════════════════════════════════════
print("\n8. JAVASCRIPT EVALUATION")
# ═══════════════════════════════════════════════════════════════════════
r = test("Get page info via JS", lambda: browser_evaluate("""JSON.stringify({
    title: document.title,
    url: window.location.href,
    links: document.querySelectorAll('a').length,
    images: document.querySelectorAll('img').length,
    forms: document.querySelectorAll('form').length,
    scripts: document.querySelectorAll('script').length,
    viewport: {w: window.innerWidth, h: window.innerHeight}
})"""))
if r:
    info = json.loads(r.get("result", "{}"))
    print(f"    Links: {info.get('links')}, Images: {info.get('images')}, Forms: {info.get('forms')}")

# ═══════════════════════════════════════════════════════════════════════
print("\n9. PERFORMANCE METRICS")
# ═══════════════════════════════════════════════════════════════════════
r = test("Get performance", lambda: browser_get_performance())
if r:
    m = r.get("metrics", {})
    print(f"    DOMContentLoaded: {m.get('domContentLoaded')}ms")
    print(f"    Load complete: {m.get('loadComplete')}ms")
    print(f"    Resources: {m.get('resourceCount')}")
    print(f"    Transfer: {m.get('totalTransferSize', 0) / 1024:.1f}KB")

# ═══════════════════════════════════════════════════════════════════════
print("\n10. COOKIES")
# ═══════════════════════════════════════════════════════════════════════
r = test("Get cookies", lambda: browser_cookies("get"))
if r:
    print(f"    Cookies: {r.get('count', 0)}")
    for c in r.get("cookies", [])[:3]:
        print(f"      → {c.get('name', '')}: {str(c.get('value', ''))[:30]}...")

# ═══════════════════════════════════════════════════════════════════════
print("\n11. TAB MANAGEMENT")
# ═══════════════════════════════════════════════════════════════════════
r = test("List tabs", lambda: browser_list_tabs())
if r:
    print(f"    Tabs: {len(r.get('tabs', []))}")

r = test("New tab with GitHub", lambda: browser_new_tab("https://github.com"))
if r:
    print(f"    Tab ID: {r.get('tab_id')}")
    print(f"    Title: {r.get('title')}")

r = test("List tabs after new", lambda: browser_list_tabs())
if r:
    for t in r.get("tabs", []):
        print(f"      [{t.get('id', '')[:8]}] {t.get('title', '')[:40]} {'<-- active' if t.get('active') else ''}")

# ═══════════════════════════════════════════════════════════════════════
print("\n12. NETWORK LOGGING")
# ═══════════════════════════════════════════════════════════════════════
r = test("Start network log", lambda: browser_network_log("start"))
r = test("Open page to generate traffic", lambda: browser_open("https://httpbin.org/get"))
r = test("Get network log", lambda: browser_network_log("get"))
if r:
    entries = r.get("entries", [])
    print(f"    Network requests: {r.get('count', 0)}")
    for e in entries[:5]:
        print(f"      {e.get('method', '')} {e.get('resource_type', '')} {e.get('url', '')[:60]}")

# ═══════════════════════════════════════════════════════════════════════
print("\n13. VIEWPORT + MOBILE")
# ═══════════════════════════════════════════════════════════════════════
r = test("Set mobile viewport (iPhone)", lambda: browser_mobile_emulate("iphone"))
if r:
    print(f"    Device: {r.get('device')}")
    print(f"    Viewport: {r.get('viewport')}")

r = test("Take mobile screenshot", lambda: browser_screenshot())
if r:
    print(f"    Screenshot: {r.get('screenshot')}")

r = test("Reset to desktop", lambda: browser_set_viewport(1920, 1080))

# ═══════════════════════════════════════════════════════════════════════
print("\n14. SCREENSHOT (full page)")
# ═══════════════════════════════════════════════════════════════════════
r = test("Open GitHub", lambda: browser_open("https://github.com/trending"))
r = test("Full page screenshot", lambda: browser_screenshot(full_page=True))
if r:
    print(f"    Screenshot: {r.get('screenshot')}")

# ═══════════════════════════════════════════════════════════════════════
print("\n15. PDF EXPORT")
# ═══════════════════════════════════════════════════════════════════════
r = test("Save page as PDF", lambda: browser_pdf())
if r:
    print(f"    PDF: {r.get('pdf')}")

# ═══════════════════════════════════════════════════════════════════════
print("\n16. NETWORK INTERCEPTION")
# ═══════════════════════════════════════════════════════════════════════
r = test("Block image requests", lambda: browser_intercept(
    enable=True, block_domains="googleads.g.doubleclick.net,pagead2.googlesyndication.com"
))
r = test("Open page with blocking", lambda: browser_open("https://www.spiegel.de"))
if r:
    print(f"    Title: {r.get('title')}")

r = test("Disable interception", lambda: browser_intercept(enable=False))

# ═══════════════════════════════════════════════════════════════════════
print("\n17. ACCESSIBILITY TREE")
# ═══════════════════════════════════════════════════════════════════════
r = test("Get accessibility snapshot", lambda: browserAccessibility_snapshot())
if r:
    snap = r.get("snapshot", {})
    print(f"    Root role: {snap.get('role', '')}")
    print(f"    Root name: {snap.get('name', '')[:50]}")
    children = snap.get("children", [])
    print(f"    Children: {len(children)}")

# ═══════════════════════════════════════════════════════════════════════
print("\n18. CLOSE TABS")
# ═══════════════════════════════════════════════════════════════════════
r = test("Close extra tab", lambda: browser_close_tab())
r = test("Final tab list", lambda: browser_list_tabs())
if r:
    print(f"    Tabs remaining: {len(r.get('tabs', []))}")

# ═══════════════════════════════════════════════════════════════════════
print("\n19. CLEANUP")
# ═══════════════════════════════════════════════════════════════════════
test("Close browser", lambda: (_close_browser(), True)[-1])

# ═══════════════════════════════════════════════════════════════════════
# PLUGIN CLASS TESTS
# ═══════════════════════════════════════════════════════════════════════
print("\n20. PLUGIN CLASS")
from data.plugins.browser import BrowserPlugin

plugin = BrowserPlugin()
test("Plugin name", lambda: plugin.name == "browser")
test("Plugin version", lambda: plugin.version == "2.0.0")
test("Plugin tools count >= 30", lambda: len(plugin.tools) >= 30)
test("Plugin tool_map count >= 30", lambda: len(plugin.tool_map) >= 30)
test("PROMPT_EXTRA length", lambda: len(PROMPT_EXTRA) > 500)

# ═══════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"RESULTS: {len(passed)} passed, {len(errors)} failed")
if errors:
    print("\nFAILED TESTS:")
    for e in errors:
        print(f"  ✗ {e}")
print("=" * 70)
sys.exit(0 if not errors else 1)

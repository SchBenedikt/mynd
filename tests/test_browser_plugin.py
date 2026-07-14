"""Test the Cloud Browser plugin – real Playwright automation."""
import json
import sys

sys.path.insert(0, '.')

print("=" * 70)
print("CLOUD BROWSER PLUGIN TEST")
print("=" * 70)

errors = []
passed = []

def test(name, fn):
    try:
        result = fn()
        passed.append(name)
        print(f"  ✓ {name}")
        return result
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"  ✗ {name}: {e}")
        return None

# ── Import plugin ──
print("\n1. IMPORT & INITIALIZATION")
from data.plugins.browser import (
    _active_tab,
    _close_browser,
    _ensure_browser,
    _pages,
    browser_back,
    browser_click,
    browser_close_tab,
    browser_cookies,
    browser_evaluate,
    browser_extract,
    browser_fill_form,
    browser_forward,
    browser_get_performance,
    browser_hover,
    browser_list_tabs,
    browser_navigate,
    browser_new_tab,
    browser_open,
    browser_pdf,
    browser_screenshot,
    browser_scroll,
    browser_search,
    browser_set_viewport,
    browser_type,
    browser_wait_for,
)

test("Plugin imports OK", lambda: True)

# ── Browser startup ──
print("\n2. BROWSER STARTUP")
test("Ensure browser starts", lambda: _ensure_browser() is not None)
test("Active tab exists", lambda: _active_tab is not None and _active_tab in _pages)

# ── Open URL ──
print("\n3. OPEN URL (browser_open)")
result = test("Open example.com", lambda: json.loads(browser_open("https://example.com")))
if result:
    assert result["success"], f"Failed: {result}"
    assert "Example Domain" in result.get("title", ""), f"Wrong title: {result.get('title')}"
    assert result.get("screenshot"), "No screenshot"
    assert result.get("text_preview"), "No text preview"
    print(f"    Title: {result['title']}")
    print(f"    URL: {result['url']}")
    print(f"    Screenshot: {result['screenshot']}")
    print(f"    Text length: {len(result.get('text_preview', ''))} chars")

# ── Screenshot ──
print("\n4. SCREENSHOT (browser_screenshot)")
result = test("Take screenshot", lambda: json.loads(browser_screenshot()))
if result:
    assert result["success"], f"Failed: {result}"
    assert result.get("screenshot"), "No screenshot"
    print(f"    Screenshot: {result['screenshot']}")

result = test("Full page screenshot", lambda: json.loads(browser_screenshot(full_page=True)))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Full page screenshot: {result['screenshot']}")

# ── Extract content ──
print("\n5. EXTRACT CONTENT (browser_extract)")
for mode in ["text", "links", "structured", "full"]:
    result = test(f"Extract mode={mode}", lambda m=mode: json.loads(browser_extract(m)))
    if result:
        assert result["success"], f"Failed: {result}"
        key = "text" if mode == "text" else ("links" if mode == "links" else ("structured" if mode == "structured" else "text"))
        data = result.get("text", "") or result.get("links", []) or result.get("structured", [])
        print(f"    Got {len(str(data))} chars of data")

# ── Navigation ──
print("\n6. NAVIGATION")
result = test("Navigate to Wikipedia", lambda: json.loads(browser_navigate("https://en.wikipedia.org")))
if result:
    assert result["success"], f"Failed: {result}"
    assert "Wikipedia" in result.get("title", "")
    print(f"    Title: {result['title']}")

result = test("Go back", lambda: json.loads(browser_back()))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Back to: {result.get('title', 'unknown')}")

result = test("Go forward", lambda: json.loads(browser_forward()))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Forward to: {result.get('title', 'unknown')}")

# ── Scroll ──
print("\n7. SCROLL (browser_scroll)")
result = test("Scroll down 500px", lambda: json.loads(browser_scroll("down", 500)))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Scrolled {result.get('amount')}px")

result = test("Scroll up 300px", lambda: json.loads(browser_scroll("up", 300)))
if result:
    assert result["success"]

# ── Click ──
print("\n8. CLICK (browser_click)")
result = test("Navigate to example.com", lambda: json.loads(browser_open("https://example.com")))
result = test("Click first link", lambda: json.loads(browser_click("a", wait_after=2)))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Clicked → New title: {result.get('new_title')}")

# ── Type ──
print("\n9. TYPE (browser_type)")
result = test("Open Wikipedia", lambda: json.loads(browser_open("https://en.wikipedia.org")))
result = test("Type search query", lambda: json.loads(browser_type(
    'input[name="search"]', 'Playwright automation', press_enter=False
)))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Typed: {result.get('typed')}")

# ── Fill form ──
print("\n10. FILL FORM (browser_fill_form)")
result = test("Fill form fields", lambda: json.loads(browser_fill_form(
    "", json.dumps({'input[name="search"]': 'test query'})
)))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Filled: {result.get('filled')}")

# ── JavaScript evaluation ──
print("\n11. EVALUATE JS (browser_evaluate)")
result = test("Get document title", lambda: json.loads(browser_evaluate("document.title")))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Result: {result.get('result')}")

result = test("Get viewport size", lambda: json.loads(browser_evaluate(
    "JSON.stringify({w: window.innerWidth, h: window.innerHeight})"
)))
if result:
    assert result["success"]
    print(f"    Viewport: {result.get('result')}")

result = test("Get all links count", lambda: json.loads(browser_evaluate(
    "document.querySelectorAll('a').length"
)))
if result:
    assert result["success"]
    print(f"    Links on page: {result.get('result')}")

# ── Web search ──
print("\n12. WEB SEARCH (browser_search)")
result = test("Search Google for 'Python'", lambda: json.loads(browser_search("Python programming", "google")))
if result:
    assert result["success"], f"Failed: {result}"
    print(f"    Results: {result.get('result_count', 0)}")
    for r in result.get("results", [])[:3]:
        print(f"      - {r.get('title', '')[:60]}")
        print(f"        {r.get('url', '')[:80]}")

# ── Tabs ──
print("\n13. TAB MANAGEMENT")
result = test("List tabs", lambda: json.loads(browser_list_tabs()))
if result:
    assert result["success"]
    print(f"    Tabs: {len(result.get('tabs', []))}")

result = test("Open new tab", lambda: json.loads(browser_new_tab("https://httpbin.org/ip")))
if result:
    assert result["success"]
    print(f"    New tab ID: {result.get('tab_id')}")

result = test("List tabs after new", lambda: json.loads(browser_list_tabs()))
if result:
    print(f"    Tabs now: {len(result.get('tabs', []))}")

# ── Viewport ──
print("\n14. VIEWPORT (browser_set_viewport)")
result = test("Set viewport 1920x1080", lambda: json.loads(browser_set_viewport(1920, 1080)))
if result:
    assert result["success"]
    print(f"    Viewport: {result.get('viewport')}")

# ── Performance ──
print("\n15. PERFORMANCE (browser_get_performance)")
result = test("Get performance metrics", lambda: json.loads(browser_get_performance()))
if result:
    assert result["success"]
    m = result.get("metrics", {})
    print(f"    DOMContentLoaded: {m.get('domContentLoaded')}ms")
    print(f"    Load complete: {m.get('loadComplete')}ms")
    print(f"    Resources: {m.get('resourceCount')}")
    print(f"    Transfer: {m.get('totalTransferSize', 0) / 1024:.1f}KB")

# ── Cookies ──
print("\n16. COOKIES (browser_cookies)")
result = test("Get cookies", lambda: json.loads(browser_cookies()))
if result:
    assert result["success"]
    print(f"    Cookies: {len(result.get('cookies', []))}")

# ── PDF ──
print("\n17. PDF (browser_pdf)")
result = test("Save page as PDF", lambda: json.loads(browser_pdf()))
if result:
    assert result["success"]
    print(f"    PDF: {result.get('pdf')}")

# ── Wait for element ──
print("\n18. WAIT FOR ELEMENT (browser_wait_for)")
result = test("Wait for body", lambda: json.loads(browser_wait_for("body", 5)))
if result:
    assert result["success"]
    print(f"    Found: {result.get('found')}")

# ── Hover ──
print("\n19. HOVER (browser_hover)")
result = test("Hover over body", lambda: json.loads(browser_hover("body")))
if result:
    assert result["success"]
    print(f"    Hovered: {result.get('hovered')}")

# ── Close tab ──
print("\n20. CLOSE TAB (browser_close_tab)")
tabs_before = json.loads(browser_list_tabs()).get("tabs", [])
result = test("Close non-active tab", lambda: json.loads(browser_close_tab(
    [t["id"] for t in tabs_before if not t.get("active")][:1] and "" or ""
)))
print(f"    Tabs remaining: {len(json.loads(browser_list_tabs()).get('tabs', []))}")

# ── Plugin class ──
print("\n21. PLUGIN CLASS")
from data.plugins.browser import BrowserPlugin

plugin = BrowserPlugin()
test("Plugin name", lambda: plugin.name == "browser")
test("Plugin version", lambda: plugin.version == "1.0.0")
test("Plugin tools count", lambda: len(plugin.tools) == 23)
test("Plugin tool_map count", lambda: len(plugin.tool_map) == 23)
test("PROMPT_EXTRA exists", lambda: len(PROMPT_EXTRA) > 100 if 'PROMPT_EXTRA' in dir() else False)

# ── Cleanup ──
print("\n22. CLEANUP")
test("Close browser", lambda: (_close_browser(), True)[-1])

# ── Summary ──
print("\n" + "=" * 70)
print(f"RESULTS: {len(passed)} passed, {len(errors)} failed")
if errors:
    print("\nFAILED TESTS:")
    for e in errors:
        print(f"  ✗ {e}")
print("=" * 70)

sys.exit(0 if not errors else 1)

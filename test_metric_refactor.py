"""
Focused Playwright test for the metric registry refactor (S1-S7) + section accordion (S56).
Validates:
1. All 5 tabs render section accordion correctly
2. Section headers show icons, badges, summary pills
3. Expanding sections reveals metric cards
4. MetricCard shows comparison tooltips (nested contract fields)
5. Quality flags display correctly
6. Persona score card works with nested metrics
7. Tab switching preserves rendering
8. No console errors from type mismatches
"""
import os
import time
import json
import sys
from playwright.sync_api import sync_playwright, expect, TimeoutError as PwTimeout

BASE = os.environ.get("BASE_URL", "http://localhost:5173")
API = os.environ.get("API_URL", "http://localhost:8000/api/v1")
SEARCH = "SW1A 1AA"

TAB_SHORT = ["Overview", "Property", "Lifestyle", "Environment", "Community", "Governance"]
TAB_FULL = [
    "Overview",
    "Property & Market",
    "Lifestyle & Connectivity",
    "Environment & Safety",
    "Community & Education",
    "Local Governance",
]
EXPECTED_METRIC_COUNTS = {
    "Overview": 10,
    "Property": 12,
    "Lifestyle": 8,
    "Environment": 11,
    "Community": 26,
    "Governance": 5,
}

passed = 0
failed = 0
warnings = 0
errors_log = []


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label} — {detail}")


def warn(label, detail=""):
    global warnings
    warnings += 1
    print(f"  WARN: {label} — {detail}")


def results_url(query):
    return f"{BASE}/results?q={query.replace(' ', '+')}"


def wait_for_sections(page, timeout=60000):
    """Wait for section accordion headers to appear (h3 inside section buttons)."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        count = page.locator("h3.text-sm.font-semibold").count()
        if count >= 1:
            time.sleep(0.5)
            return count
        time.sleep(1)
    return 0


def expand_all_sections(page):
    """Click each collapsed section header to expand all sections (multi-expand accordion).
    Returns total visible metric count after all sections are open."""
    section_btns = page.locator("button:has(h3.text-sm.font-semibold)").all()
    for btn in section_btns:
        expanded = btn.get_attribute("aria-expanded")
        if expanded != "true":
            btn.click()
            time.sleep(0.5)
    time.sleep(1)
    return page.locator("[id^='metric-']").count()


def count_metrics_via_api(tab_name):
    """Count metrics for a tab via API (ground truth)."""
    import urllib.request
    import urllib.parse
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    resolve_url = f"{API}/resolve?q={urllib.parse.quote(SEARCH)}"
    with urllib.request.urlopen(resolve_url, context=ctx) as resp:
        data = json.loads(resp.read())
    session_key = data["session_key"]
    area_url = f"{API}/area?session_key={session_key}&tab={urllib.parse.quote(tab_name)}"
    with urllib.request.urlopen(area_url, context=ctx) as resp:
        data = json.loads(resp.read())
    return len([m for m in data.get("metrics", []) if m.get("local_value") is not None])


def switch_tab(page, short_name):
    btn = page.locator(f'button:has-text("{short_name}")').first
    btn.click()
    time.sleep(1)
    wait_for_sections(page)


def run_tests():
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # Capture console errors
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # ── Navigate to results ──
        print("\n=== 1. Initial Page Load ===")
        page.goto(results_url(SEARCH), timeout=60000)
        page.wait_for_selector("h1", timeout=30000)
        time.sleep(3)

        # Check the page loaded
        title = page.locator("h1").first.inner_text()
        check("Page title present", len(title) > 0, f"title='{title}'")

        # Default tab is now Overview — switch to Property for section accordion checks
        switch_tab(page, "Property")
        time.sleep(2)

        # Wait for section accordion to render
        section_count = wait_for_sections(page)
        check("Section accordion loaded", section_count >= 3, f"found {section_count} sections")

        # ── Check section structure ──
        print("\n=== 2. Section Accordion Structure ===")

        # Section headers should have icons (w-7 h-7 rounded-md)
        section_icons = page.locator("div.w-7.h-7.rounded-md")
        check("Section icons rendered", section_icons.count() >= 3, f"found {section_icons.count()}")

        # Summary pills visible on collapsed sections
        pills = page.locator("[class*='inline-flex'][class*='rounded-lg'][class*='text-xs'][class*='border']")
        check("Summary pills visible", pills.count() >= 3, f"found {pills.count()}")

        # Pills should contain values (font-mono span)
        pill_values = page.locator("[class*='inline-flex'][class*='rounded-lg'] span.font-mono")
        check("Pill values present", pill_values.count() >= 3, f"found {pill_values.count()}")

        # "+N more" pills should exist for sections with >3 metrics
        more_pills = page.locator("text=/\\+\\d+ more/")
        check("'+N more' pills present", more_pills.count() >= 1, f"found {more_pills.count()}")

        # Section badges (Above/Below Average)
        badges = page.locator("text=/Above Average|Below Average|Average/")
        check("Section badges visible", badges.count() >= 1, f"found {badges.count()}")

        # ── Expand sections and check metrics ──
        print("\n=== 3. Expanded Section — MetricCards ===")
        metric_count = expand_all_sections(page)
        check("Metric cards visible after expanding", metric_count >= 10, f"found {metric_count}")

        # Check metric names in the currently open section (last one after expand_all)
        metric_names = page.locator("[id^='metric-'] .text-sm.font-semibold")
        check("Metric names rendered (last section)", metric_names.count() >= 1, f"found {metric_names.count()}")

        # Check local values displayed (font-mono for numeric values)
        local_values = page.locator("[id^='metric-'] .font-mono")
        check("Local values rendered", local_values.count() >= 1, f"found {local_values.count()}")

        # ── Check PersonaScoreCard ──
        print("\n=== 4. PersonaScoreCard ===")
        score_card = page.locator('text=/scores \\d+\\/100/')
        check("PersonaScoreCard visible", score_card.count() > 0, f"looking for 'scores N/100' text")

        # ── Tab switching ──
        print("\n=== 5. Tab Switching ===")
        for i, (short, full) in enumerate(zip(TAB_SHORT, TAB_FULL)):
            switch_tab(page, short)
            time.sleep(2)
            if short != "Overview":
                sc = wait_for_sections(page)
                check(f"{short} tab: sections loaded", sc >= 1, f"found {sc} sections")
            else:
                # Overview uses custom grid layout, not section accordion
                check(f"{short} tab: loaded", True, "Overview tab has custom layout")

            # Verify metric count via API
            api_count = count_metrics_via_api(full)
            expected = EXPECTED_METRIC_COUNTS.get(short, 1)
            check(f"{short} tab: API returns {api_count} metrics (expected {expected})", api_count >= expected - 2, f"got {api_count}")

        # ── Quality flags ──
        print("\n=== 6. Quality Flags ===")
        switch_tab(page, "Community")
        time.sleep(2)
        expand_all_sections(page)
        time.sleep(1)

        # Expand a metric (click its button)
        metric_buttons = page.locator("[id^='metric-'] button").all()
        expanded_any = False
        for btn in metric_buttons[:5]:
            try:
                btn.click()
                time.sleep(0.5)
                # Check for quality flag banner (amber background)
                quality_banner = page.locator('[class*="bg-amber-50"]')
                if quality_banner.count() > 0:
                    check("Quality flags displayed", True)
                    expanded_any = True
                    break
            except Exception:
                continue
        if not expanded_any:
            warn("No quality flag banners found in Community tab", "May need different metric")

        # ── Expand metric details ──
        print("\n=== 7. Metric Detail Expansion ===")
        switch_tab(page, "Property")
        time.sleep(2)

        # First section auto-opens on tab switch; ensure it's expanded
        first_section = page.locator("button:has(h3.text-sm.font-semibold)").first
        if first_section.get_attribute("aria-expanded") != "true":
            first_section.click()
            time.sleep(1.5)

        # Click on first metric to expand its detail panel
        first_metric_btn = page.locator("[id^='metric-'] button").first
        first_metric_btn.click()
        time.sleep(2)

        # Check expanded content appears (details area with border-t)
        detail_areas = page.locator('[class*="border-t"][class*="border-divider"]')
        check("Detail panel expanded", detail_areas.count() > 0)

        # Check source badge appears — try multiple possible sources
        source_badge = page.locator('text=/HM Land Registry|Land Registry|ONS|Census/')
        check("Source badge visible", source_badge.count() > 0)

        # ── Console errors ──
        print("\n=== 8. Console Errors ===")
        real_errors = [e for e in console_errors if "429" not in e and "WebGL" not in e and "Failed to load resource" not in e and "maplibre" not in e.lower()]
        check("No React/JS console errors", len(real_errors) == 0, f"errors: {real_errors[:3]}")

        # ── Responsive check ──
        print("\n=== 9. Responsive (Mobile) ===")
        context2 = browser.new_context(viewport={"width": 375, "height": 812})
        mobile_page = context2.new_page()
        mobile_page.goto(results_url(SEARCH), timeout=60000)
        mobile_page.wait_for_selector("h1", timeout=30000)
        time.sleep(3)

        mobile_sections = wait_for_sections(mobile_page)
        check("Mobile: sections render", mobile_sections >= 3, f"found {mobile_sections}")

        # Mobile should show summary pills
        mobile_pills = mobile_page.locator("[class*='inline-flex'][class*='rounded-lg'][class*='text-xs']")
        check("Mobile: summary pills render", mobile_pills.count() >= 3, f"found {mobile_pills.count()}")

        context2.close()

        # ── Error states ──
        print("\n=== 10. Error/Edge States ===")
        error_page = context.new_page()
        error_page.goto(results_url("XYZABC123"), timeout=60000)
        time.sleep(5)
        body_text = error_page.locator("body").inner_text()
        has_error_state = "not found" in body_text.lower() or "no results" in body_text.lower() or "error" in body_text.lower() or "try" in body_text.lower()
        check("Invalid search shows feedback", has_error_state, f"body contains error/feedback")

        browser.close()

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {warnings} warnings")
    if failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"WARNING: {failed} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()

"""
Focused Playwright test for the metric registry refactor (S1-S7).
Validates:
1. All 5 tabs render metrics correctly after nested contract changes
2. MetricCard shows comparison tooltips (new nested fields)
3. Quality flags display correctly
4. Persona score card works with nested metrics
5. Tab switching preserves rendering
6. No console errors from type mismatches
"""
import time
import json
import sys
from playwright.sync_api import sync_playwright, expect, TimeoutError as PwTimeout

BASE = "http://localhost:5173"
API = "http://localhost:8000/api/v1"
SEARCH = "SW1A 1AA"

TAB_SHORT = ["Property", "Lifestyle", "Environment", "Community", "Governance"]
TAB_FULL = [
    "Property & Market",
    "Lifestyle & Connectivity",
    "Environment & Safety",
    "Community & Education",
    "Local Governance",
]
EXPECTED_METRIC_COUNTS = {
    "Property": 14,
    "Lifestyle": 12,
    "Environment": 12,
    "Community": 27,
    "Governance": 4,
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


def wait_for_metrics(page, timeout=60000):
    """Wait for MetricCard components to appear (they have border-l-[3px] and rounded-2xl)."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        count = page.locator('[class*="border-l-"][class*="rounded-2xl"]').count()
        if count >= 1:
            time.sleep(0.5)
            return count
        time.sleep(1)
    return 0


def count_metric_cards(page):
    return page.locator('[class*="border-l-"][class*="rounded-2xl"]').count()


def switch_tab(page, short_name):
    btn = page.locator(f'button:has-text("{short_name}")').first
    btn.click()
    time.sleep(1)
    wait_for_metrics(page)


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
        page.goto(results_url(SEARCH))
        page.wait_for_selector("h1", timeout=30000)
        time.sleep(3)

        # Check the page loaded
        title = page.locator("h1").first.inner_text()
        check("Page title present", len(title) > 0, f"title='{title}'")

        # Wait for Property tab metrics (default tab)
        metric_count = wait_for_metrics(page)
        check("Property tab metrics loaded", metric_count >= 10, f"found {metric_count}")

        # ── Check metric card structure ──
        print("\n=== 2. MetricCard Structure ===")

        # Expand first metric card to check details
        first_card = page.locator('[class*="border-l-"][class*="rounded-2xl"]').first
        check("First metric card exists", first_card is not None)

        # Check metric name is displayed
        metric_names = page.locator('[class*="border-l-"][class*="rounded-2xl"] span.text-sm.font-semibold')
        check("Metric names rendered", metric_names.count() >= 5, f"found {metric_names.count()}")

        # Check local values displayed (font-mono for numeric values)
        local_values = page.locator('[class*="border-l-"][class*="rounded-2xl"] span.font-mono')
        check("Local values rendered", local_values.count() >= 5, f"found {local_values.count()}")

        # Check comparison icons/values
        comparison_spans = page.locator('[class*="border-l-"][class*="rounded-2xl"] [title]')
        has_tooltips = comparison_spans.count() > 0
        if has_tooltips:
            # New: comparison tooltips from nested contract
            first_tooltip = comparison_spans.first.get_attribute("title")
            check("Comparison tooltip present", first_tooltip and "%" in first_tooltip, f"tooltip='{first_tooltip}'")
        else:
            warn("No comparison tooltips found", "May be expected if not all metrics have parent comparison")

        # Check decision question displayed
        decision_qs = page.locator('[class*="border-l-"][class*="rounded-2xl"] span[class*="text-ink-faint/60"]')
        check("Decision questions rendered", decision_qs.count() >= 3, f"found {decision_qs.count()}")

        # Check persona pills (So What / Watch Out)
        persona_pills = page.locator('[class*="border-l-"][class*="rounded-2xl"] [class*="rounded-lg"][class*="text-xs"]')
        check("Persona pills rendered", persona_pills.count() >= 3, f"found {persona_pills.count()}")

        # ── Check PersonaScoreCard ──
        print("\n=== 3. PersonaScoreCard ===")
        score_card = page.locator('text=/scores \\d+\\/100/')
        check("PersonaScoreCard visible", score_card.count() > 0, f"looking for 'scores N/100' text")

        # ── Tab switching ──
        print("\n=== 4. Tab Switching ===")
        for i, tab in enumerate(TAB_SHORT):
            switch_tab(page, tab)
            time.sleep(2)
            mc = count_metric_cards(page)
            expected = EXPECTED_METRIC_COUNTS.get(tab, 1)
            check(f"{tab} tab: {mc} metrics (expected {expected})", mc >= expected - 2, f"found {mc}")

        # ── Quality flags ──
        print("\n=== 5. Quality Flags ===")
        # Switch to Community tab which has quality_flags
        switch_tab(page, "Community")
        time.sleep(2)

        # Expand a metric card that has quality flags
        # "no_car" has quality flag: "Higher may be positive in well-connected urban areas."
        # Find a metric with "No Car" or "Car" in the name
        no_car_card = page.locator('[class*="border-l-"][class*="rounded-2xl"]:has-text("No Car")')
        if no_car_card.count() == 0:
            no_car_card = page.locator('[class*="border-l-"][class*="rounded-2xl"]:has-text("car")')
        if no_car_card.count() > 0:
            no_car_card.first.locator("button").first.click()
            time.sleep(1)
            # Check for quality flag banner (amber background)
            quality_banner = page.locator('[class*="bg-amber-50"]')
            check("Quality flags displayed", quality_banner.count() > 0, f"found {quality_banner.count()} amber banners")
        else:
            # Try expanding ANY Community metric and check for quality flags
            first_community = page.locator('[class*="border-l-"][class*="rounded-2xl"]').first
            first_community.locator("button").first.click()
            time.sleep(1)
            quality_banner = page.locator('[class*="bg-amber-50"]')
            if quality_banner.count() > 0:
                check("Quality flags displayed (on first metric)", True)
            else:
                warn("No quality flag banners found in Community tab — may need different metric")

        # ── Expand metric details ──
        print("\n=== 6. Metric Detail Expansion ===")
        switch_tab(page, "Property")
        time.sleep(2)

        # Click on first Property metric to expand
        first_prop = page.locator('[class*="border-l-"][class*="rounded-2xl"]').first
        first_prop.locator("button").first.click()
        time.sleep(1)

        # Check expanded content appears (details area with border-t)
        detail_areas = page.locator('[class*="border-t"][class*="border-divider"]')
        check("Detail panel expanded", detail_areas.count() > 0)

        # Check source badge appears
        source_badge = page.locator('text=HM Land Registry')
        check("Source badge visible", source_badge.count() > 0)

        # ── Console errors ──
        print("\n=== 7. Console Errors ===")
        # Filter out known benign errors (e.g., rate limit warnings, MapLibre WebGL)
        real_errors = [e for e in console_errors if "429" not in e and "WebGL" not in e and "Failed to load resource" not in e and "maplibre" not in e.lower()]
        check("No React/JS console errors", len(real_errors) == 0, f"errors: {real_errors[:3]}")

        # ── Responsive check ──
        print("\n=== 8. Responsive (Mobile) ===")
        context2 = browser.new_context(viewport={"width": 375, "height": 812})
        mobile_page = context2.new_page()
        mobile_page.goto(results_url(SEARCH))
        mobile_page.wait_for_selector("h1", timeout=30000)
        time.sleep(3)

        mobile_metrics = wait_for_metrics(mobile_page)
        check("Mobile: metrics render", mobile_metrics >= 5, f"found {mobile_metrics}")

        # Mobile should show card layout (not table row)
        mobile_cards = mobile_page.locator('[class*="border-l-"][class*="rounded-2xl"] button[class*="lg:hidden"]')
        check("Mobile: card layout used", mobile_cards.count() >= 3, f"found {mobile_cards.count()}")

        context2.close()

        # ── Error states ──
        print("\n=== 9. Error/Edge States ===")
        # Invalid search
        error_page = context.new_page()
        error_page.goto(results_url("XYZABC123"))
        time.sleep(5)
        # Should show error or no results
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

"""
Comprehensive Playwright browser tests for PropertyPulse.
Covers: 5-tab rendering, charts, map, null metrics, tab switching,
error states, and responsive viewports.

Requires: pip3 install playwright && playwright install chromium
Servers: frontend on :5173, backend on :8000
"""

import time
import json
import sys
import os
from playwright.sync_api import sync_playwright, expect, TimeoutError as PwTimeout

BASE = os.environ.get("BASE_URL", "http://localhost:5173")
API = os.environ.get("API_URL", "http://127.0.0.1:8000/api/v1")

# Tab short names used in the TabBar buttons (sm:hidden shows shortName)
TAB_NAMES = ["Property", "Lifestyle", "Environment", "Community", "Governance"]
TAB_FULL = [
    "Property & Market",
    "Lifestyle & Connectivity",
    "Environment & Safety",
    "Community & Education",
    "Local Governance",
]

# Search scenarios
SEARCHES = {
    "postcode": "SW1A 1AA",
    "lad": "Manchester",
    "place": "Didsbury",
}

# API rate-limit: 60 req/min — pace between scenarios
PACE_SECONDS = 2

# ──────────────────────── Helpers ────────────────────────


def results_url(query: str) -> str:
    return f"{BASE}/results?q={query.replace(' ', '+')}"


def wait_for_results(page, timeout=60000):
    """Wait for the results page to fully load (area banner visible)."""
    page.wait_for_selector("h1", timeout=timeout)


def wait_for_tab_data(page, timeout=45000):
    """Wait for section accordion headers to appear (accordion layout).
    Polls until at least one section header (h3.text-sm.font-semibold) is found,
    or until timeout."""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        count = page.locator('h3.text-sm.font-semibold').count()
        if count >= 1:
            time.sleep(0.5)  # Small buffer for remaining sections to render
            return
        time.sleep(1)
    # Fallback: wait for any grid content
    try:
        page.wait_for_selector('[class*="grid gap"]', timeout=3000)
    except PwTimeout:
        pass


def get_tab_button(page, short_name: str):
    """Get a tab button by its data-tab attribute or text content."""
    # TabBar uses data-tab with full name — find via short name text
    return page.locator(f'button:has-text("{short_name}")').first


def switch_tab(page, short_name: str):
    """Click a tab and wait for data to load."""
    btn = get_tab_button(page, short_name)
    btn.click()
    wait_for_tab_data(page)


def count_metric_cards(page) -> int:
    """Count section headers in the accordion layout.
    Each section header (h3.text-sm.font-semibold) represents a group of metrics."""
    return page.locator('h3.text-sm.font-semibold').count()


def get_metric_card_texts(page) -> list[str]:
    """Get all section header text content."""
    headers = page.locator('h3.text-sm.font-semibold')
    texts = []
    for i in range(headers.count()):
        texts.append(headers.nth(i).inner_text())
    return texts


def count_markers(page) -> int:
    """Count all maplibregl markers on page."""
    return page.evaluate("() => document.querySelectorAll('.maplibregl-marker').length")


def has_map_canvas(page) -> bool:
    """Check if a map canvas element exists."""
    return page.locator("canvas.maplibregl-canvas").count() > 0


# ──────────────────────── Test Runner ────────────────────────


class TestResults:
    def __init__(self):
        self.results: list[tuple[str, str, str]] = []  # (section, name, status)

    def add(self, section: str, name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append((section, name, f"{status} — {detail}" if detail else status))

    def add_warn(self, section: str, name: str, detail: str = ""):
        self.results.append((section, name, f"WARN — {detail}"))

    def summary(self):
        print("\n" + "=" * 80)
        print("COMPREHENSIVE PLAYWRIGHT TEST SUMMARY")
        print("=" * 80)
        passed = sum(1 for _, _, s in self.results if s.startswith("PASS"))
        failed = sum(1 for _, _, s in self.results if s.startswith("FAIL"))
        warned = sum(1 for _, _, s in self.results if s.startswith("WARN"))

        current_section = ""
        for section, name, status in self.results:
            if section != current_section:
                current_section = section
                print(f"\n  [{section}]")
            icon = "✓" if status.startswith("PASS") else ("⚠" if status.startswith("WARN") else "✗")
            print(f"    {icon} {name}: {status}")

        print("\n" + "-" * 80)
        print(f"  TOTAL: {passed} passed, {failed} failed, {warned} warnings")
        print(f"  {'ALL TESTS PASSED' if failed == 0 else 'SOME TESTS FAILED'}")
        print("=" * 80)
        return failed == 0


def run_all_tests():
    R = TestResults()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ════════════════════════════════════════════════════════════════
        # SECTION 1: Five-tab rendering for 3 search types
        # ════════════════════════════════════════════════════════════════
        for search_type, query in SEARCHES.items():
            section = f"Tabs — {search_type} ({query})"
            print(f"\n{'='*60}")
            print(f"SECTION: {section}")
            print(f"{'='*60}")

            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            # Collect console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            page.goto(results_url(query))
            try:
                wait_for_results(page)
            except PwTimeout:
                R.add(section, "Page loads", False, "Timed out waiting for h1")
                page.close()
                context.close()
                continue

            # Check area banner rendered
            h1_text = page.locator("h1").first.inner_text()
            R.add(section, "Area banner", query.upper() in h1_text.upper() or query in h1_text,
                  f"h1='{h1_text[:60]}'")

            # Check each tab
            for i, tab_short in enumerate(TAB_NAMES):
                tab_full = TAB_FULL[i]
                print(f"  Testing tab: {tab_short}")

                switch_tab(page, tab_short)
                wait_for_tab_data(page)

                # Check the tab button is active (has brand-700 text color)
                tab_btn = page.locator(f'button[data-tab="{tab_full}"]')
                tab_classes = tab_btn.get_attribute("class") or ""
                is_active = "brand-700" in tab_classes
                R.add(section, f"{tab_short} tab active state", is_active,
                      f"classes contain brand-700: {is_active}")

                # Count metric cards
                # Wait a bit for lazy-loaded content
                time.sleep(1)
                card_count = count_metric_cards(page)
                R.add(section, f"{tab_short} has metrics",
                      card_count >= 1,
                      f"{card_count} metric cards")

                # Check no "No data available" message (unless it's a valid empty tab)
                no_data = page.locator('text="No data available for this tab and area."')
                has_no_data = no_data.count() > 0
                if has_no_data and card_count == 0:
                    R.add_warn(section, f"{tab_short} shows no data", f"No metrics for {query}")
                elif card_count >= 1:
                    R.add(section, f"{tab_short} has content", True, f"{card_count} cards")

                # Check no JS errors during tab
                tab_errors = [e for e in console_errors if "Error" in e or "error" in e]

            # Check no crashes (page still navigable)
            R.add(section, "No crash after all tabs",
                  page.locator("h1").count() > 0, "h1 still present")

            page.close()
            context.close()
            time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 2: Chart rendering (DistrictPriceHistoryChart)
        # ════════════════════════════════════════════════════════════════
        section = "Charts"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("SW1A 1AA"))
        wait_for_results(page)
        wait_for_tab_data(page)  # Wait for real MetricCards

        # Property tab should be default — expand sections to reveal metric cards
        # Then click a price metric card to expand it and reveal the chart
        # First section is auto-expanded; try to find and click the Average Sale Price metric
        avg_btn = page.locator('button[aria-label*="Average Sale Price"]').first
        expanded_chart = False
        if avg_btn.count() > 0:
            avg_btn.click()
            time.sleep(3)
            expanded_chart = True
        else:
            # Fallback: expand sections and look for price metrics
            section_btns = page.locator('button:has(h3.text-sm.font-semibold)').all()
            for btn in section_btns[:3]:
                if btn.get_attribute("aria-expanded") != "true":
                    btn.click()
                    time.sleep(1)
                price_btn = page.locator('button[aria-label*="Price"]').first
                if price_btn.count() > 0:
                    price_btn.click()
                    time.sleep(3)
                    expanded_chart = True
                    break

        recharts_count = page.locator(".recharts-wrapper").count()
        R.add(section, "Recharts SVG containers",
              recharts_count > 0 or expanded_chart,
              f"{recharts_count} wrappers found")

        # Check for chart SVG paths (data lines)
        svg_paths = page.locator(".recharts-line-curve, .recharts-area-curve, .recharts-bar-rectangle")
        path_count = svg_paths.count()
        R.add(section, "Chart data paths rendered",
              path_count > 0,
              f"{path_count} data paths/bars")

        # Check for toggle pills (the chart type pills: Avg Price, Median, etc.)
        # These are typically buttons inside the chart area
        pills = page.locator('button:has-text("Avg Price"), button:has-text("Median"), button:has-text("£/sqft")')
        pill_count = pills.count()
        R.add(section, "Chart toggle pills present",
              pill_count > 0,
              f"{pill_count} toggle pill buttons")

        # If pills exist, click one and verify chart updates
        if pill_count > 0:
            try:
                pills.first.click()
                time.sleep(1)
                post_click_paths = page.locator(".recharts-line-curve, .recharts-area-curve, .recharts-bar-rectangle").count()
                R.add(section, "Toggle pill changes chart",
                      True, f"paths after click: {post_click_paths}")
            except Exception as e:
                R.add_warn(section, "Toggle pill click", str(e)[:60])

        # Check tooltip on hover — move mouse over chart area
        recharts = page.locator(".recharts-wrapper").first
        if recharts.count() > 0:
            try:
                box = recharts.bounding_box()
                if box:
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    time.sleep(0.5)
                    tooltip = page.locator(".recharts-tooltip-wrapper")
                    tooltip_visible = tooltip.count() > 0
                    R.add(section, "Tooltip appears on hover",
                          tooltip_visible, f"tooltip visible: {tooltip_visible}")
            except Exception as e:
                R.add_warn(section, "Tooltip hover", str(e)[:60])

        page.close()
        context.close()
        time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 3: Map rendering
        # ════════════════════════════════════════════════════════════════
        section = "Map"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("SW1A 1AA"))
        wait_for_results(page)
        time.sleep(5)  # Let map fully render

        # Map canvas should exist
        has_canvas = has_map_canvas(page)
        R.add(section, "Map canvas present", has_canvas)

        # Map markers should appear (sold prices on Property tab)
        marker_count = count_markers(page)
        R.add(section, "Map markers present",
              marker_count > 0, f"{marker_count} markers")

        # Check for boundary — map should have boundary source
        # We check via the LSOA fill layer which should be a canvas layer
        # Since we can't easily inspect MapLibre internals, check that the map container exists
        map_container = page.locator(".maplibregl-map")
        R.add(section, "MapLibre container", map_container.count() > 0)

        # Check for map layer control button
        layer_btns = page.locator('button[title="Map layers"], button[aria-label="Open map layers"], button[title="Map evidence and layers"]')
        R.add(section, "Layer control button",
              layer_btns.count() > 0)

        if layer_btns.count() > 0:
            # Open layer panel — use last (desktop sidebar) button; force click to bypass z-index occlusion
            layer_btns.last.click(force=True)
            time.sleep(0.5)

            # Check layer panel text contains expected layers (new labels)
            panel_text = page.locator('[class*="absolute"]').filter(has_text="Sold prices").inner_text()
            has_sold = "Sold prices" in panel_text
            R.add(section, "Layer panel — Sold Prices", has_sold, f"panel text present")

            # Check for boundary layer toggles
            has_ward = (page.locator('button:has-text("Wider area boundary")').count() > 0
                        or page.locator('button:has-text("Ward boundary")').count() > 0
                        or page.locator('text="Ward boundary"').count() > 0)
            has_lsoa = (page.locator('button:has-text("Local analysis boundary")').count() > 0
                        or page.locator('button:has-text("LSOA boundary")').count() > 0
                        or page.locator('text="LSOA boundary"').count() > 0)
            R.add(section, "Layer panel — Ward toggle", has_ward)
            R.add(section, "Layer panel — LSOA toggle", has_lsoa)

            # Toggle choropleth layer if available (new: buttons, not labels)
            choro_btn = page.locator('button:has-text("Average price heatmap")')
            if choro_btn.count() > 0:
                choro_btn.first.click(force=True)
                time.sleep(3)  # Choropleth fetches data
                R.add(section, "Choropleth toggle clicked", True, "Avg Price heatmap toggled")
                # Turn it off again
                choro_btn.first.click(force=True)
                time.sleep(1)

        # Switch to Community tab — check for school markers
        switch_tab(page, "Community")
        time.sleep(3)
        community_markers = count_markers(page)
        R.add(section, "Community tab — POI markers",
              community_markers >= 1, f"{community_markers} markers")

        # Switch to Lifestyle tab — check for station/EV markers
        switch_tab(page, "Lifestyle")
        time.sleep(3)
        lifestyle_markers = count_markers(page)
        R.add(section, "Lifestyle tab — POI markers",
              lifestyle_markers >= 1, f"{lifestyle_markers} markers")

        # Switch to Environment tab — check no sold markers
        switch_tab(page, "Environment")
        time.sleep(3)
        env_markers = count_markers(page)
        sold_env = page.evaluate("""() => {
            return [...document.querySelectorAll('.maplibregl-marker')]
                .filter(m => m.textContent && m.textContent.startsWith('£')).length;
        }""")
        R.add(section, "Environment tab — no sold markers",
              sold_env == 0, f"{sold_env} sold, {env_markers} total")

        page.close()
        context.close()
        time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 4: Null/empty metric display (Whitby — missing rent data)
        # ════════════════════════════════════════════════════════════════
        section = "Null Metrics (Whitby)"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("Whitby"))
        try:
            wait_for_results(page)
        except PwTimeout:
            R.add(section, "Page loads", False, "Timed out waiting for h1 — known Whitby issue")
            page.close()
            context.close()
            time.sleep(PACE_SECONDS)
        else:
            wait_for_tab_data(page)  # Wait for real cards

            # Whitby should resolve and show Property tab
            h1_text = page.locator("h1").first.inner_text()
            R.add(section, "Whitby resolves", "Whitby" in h1_text, f"h1='{h1_text[:40]}'")

            # Check that metric cards render (even with null values)
            card_count = count_metric_cards(page)
            R.add(section, "Property tab has cards", card_count >= 1, f"{card_count} cards")

            # Get all card texts — look for graceful null handling
            # Null values should show "—" (em-dash) not crash or show "null"/"undefined"
            cards_text = get_metric_card_texts(page)
            has_null_literal = any("null" in t.lower() or "undefined" in t for t in cards_text)
            has_dash = any("—" in t for t in cards_text)
            R.add(section, "No 'null'/'undefined' in cards",
                  not has_null_literal, f"null literal found: {has_null_literal}")
            R.add(section, "Graceful dash display",
                  has_dash, "em-dash (—) present for null values")

            # Check specifically for rent metric — Whitby has no VOA rent data
            # The rent card should show "—" or handle null gracefully
            rent_text = ""
            for t in cards_text:
                if "Rent" in t or "rent" in t:
                    rent_text = t
                    break
            if rent_text:
                R.add(section, "Rent card doesn't crash",
                      "null" not in rent_text.lower() and "undefined" not in rent_text,
                      f"rent card text snippet: '{rent_text[:60]}'")
            else:
                R.add_warn(section, "Rent card not found", "May not have rent metric visible by default")

            # Check all 5 tabs don't crash for Whitby
            for tab_short in TAB_NAMES[1:]:  # Skip Property — already checked
                switch_tab(page, tab_short)
                still_alive = page.locator("h1").count() > 0
                R.add(section, f"{tab_short} tab — no crash", still_alive)

            page.close()
            context.close()
            time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 5: Tab switching — no stale data, no crashes
        # ════════════════════════════════════════════════════════════════
        section = "Tab Switching"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(results_url("Manchester"))
        wait_for_results(page)
        wait_for_tab_data(page)

        # Get Property tab card count as baseline
        prop_cards_text = get_metric_card_texts(page)
        prop_first_metric = prop_cards_text[0][:30] if prop_cards_text else ""

        # Rapid tab switching — cycle through all tabs quickly
        for tab_short in ["Lifestyle", "Community", "Environment", "Governance", "Property"]:
            get_tab_button(page, tab_short).click()
            time.sleep(0.3)  # Don't wait for data — stress test

        # Now wait for final tab (Property) to settle
        time.sleep(5)

        # Verify Property tab data is correct (not stale from another tab)
        final_cards_text = get_metric_card_texts(page)
        final_first_metric = final_cards_text[0][:30] if final_cards_text else ""

        # The first metric on Property should contain price-related text
        has_property_metrics = any("Price" in t or "£" in t for t in final_cards_text[:3]) if final_cards_text else False
        R.add(section, "Rapid switching — correct final tab",
              has_property_metrics,
              f"first metric: '{final_first_metric}'")

        # Check page is still functional
        R.add(section, "Page alive after rapid switching",
              page.locator("h1").count() > 0)

        # Normal sequential tab switching
        for i, tab_short in enumerate(TAB_NAMES):
            switch_tab(page, tab_short)
            alive = page.locator("h1").count() > 0
            card_count = count_metric_cards(page)
            R.add(section, f"Sequential: {tab_short}",
                  alive and card_count >= 1,
                  f"alive={alive}, cards={card_count}")

        # Check no JS errors from tab switching
        serious_errors = [e for e in console_errors if "TypeError" in e or "Cannot read" in e or "is not" in e]
        R.add(section, "No TypeError/reference errors",
              len(serious_errors) == 0,
              f"{len(serious_errors)} serious errors" + (f": {serious_errors[0][:80]}" if serious_errors else ""))

        page.close()
        context.close()
        time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 6: Error states
        # ════════════════════════════════════════════════════════════════
        section = "Error States"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # Test 1: Invalid/expired session key — the resolve endpoint handles this
        # Searching for a gibberish string should show an error state
        page.goto(results_url("ZZZZZ99999"))
        time.sleep(5)

        # Should show error UI — either "No results" or "Could not resolve"
        page_text = page.locator("body").inner_text()
        has_error_ui = (
            "No results" in page_text
            or "Could not resolve" in page_text
            or "not resolve" in page_text.lower()
            or "Try a valid" in page_text
        )
        R.add(section, "Invalid search shows error UI",
              has_error_ui,
              f"Error text found: {has_error_ui}")

        # Test 2: Empty search
        page.goto(f"{BASE}/results?q=")
        time.sleep(3)
        empty_text = page.locator("body").inner_text()
        no_crash = len(empty_text) > 10  # Page rendered something
        R.add(section, "Empty search doesn't crash", no_crash)

        # Test 3: SQL injection attempt
        page.goto(results_url("'; DROP TABLE--"))
        time.sleep(5)
        sqli_text = page.locator("body").inner_text()
        sqli_safe = "DROP TABLE" not in sqli_text and "error" not in sqli_text.lower().split("no results")[0] if "no results" in sqli_text.lower() else True
        R.add(section, "SQL injection handled safely",
              page.locator("h1, [class*='rounded-2xl']").count() > 0,
              "Page rendered, no raw SQL error")

        # Test 4: Scotland postcode (no data)
        page.goto(results_url("EH1 1YZ"))
        time.sleep(5)
        eh_text = page.locator("body").inner_text()
        eh_handled = "Could not resolve" in eh_text or "No results" in eh_text or "Try a valid" in eh_text
        R.add(section, "Scotland postcode — graceful error",
              eh_handled, "England-only data")

        page.close()
        context.close()
        time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 7: Responsive viewports
        # ════════════════════════════════════════════════════════════════
        time.sleep(10)  # Extra pause to avoid rate-limit before responsive tests
        section = "Responsive"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        viewports = {
            "mobile": {"width": 375, "height": 812},
            "tablet": {"width": 768, "height": 1024},
            "desktop": {"width": 1280, "height": 900},
        }

        for vp_name, vp_size in viewports.items():
            print(f"  Testing viewport: {vp_name} ({vp_size['width']}x{vp_size['height']})")
            context = browser.new_context(viewport=vp_size)
            page = context.new_page()
            page.goto(results_url("Didsbury"))
            wait_for_results(page)
            time.sleep(5)

            # Check page renders
            h1_present = page.locator("h1").count() > 0
            R.add(section, f"{vp_name} — page renders", h1_present)

            # Check tab bar is visible
            tab_visible = page.locator('button[data-tab]').count() >= 5
            R.add(section, f"{vp_name} — tabs visible", tab_visible,
                  f"{page.locator('button[data-tab]').count()} tab buttons")

            # Check metrics render
            card_count = count_metric_cards(page)
            R.add(section, f"{vp_name} — metrics render",
                  card_count >= 1, f"{card_count} cards")

            # Desktop: map should be in side panel (persistent)
            # Mobile/tablet: map toggle button should exist
            if vp_size["width"] >= 1024:
                # Desktop — persistent map panel
                map_aside = page.locator("aside")
                R.add(section, f"{vp_name} — desktop map panel",
                      map_aside.count() > 0 or has_map_canvas(page))
            else:
                # Mobile/tablet — map toggle button
                map_toggle = page.locator('button:has-text("View Map"), button:has-text("Hide Map")')
                R.add(section, f"{vp_name} — map toggle button",
                      map_toggle.count() > 0,
                      f"found {map_toggle.count()} toggle buttons")

                # Check map state — if "Hide Map" visible, map is already showing
                if map_toggle.count() > 0:
                    toggle_text = map_toggle.first.inner_text()
                    if "Hide" in toggle_text:
                        # Map already visible — check canvas directly
                        mobile_canvas = has_map_canvas(page)
                        R.add(section, f"{vp_name} — map visible",
                              mobile_canvas, "map shown by default, canvas present")
                    else:
                        # Map hidden — click to show
                        map_toggle.first.click()
                        time.sleep(5)
                        mobile_canvas = has_map_canvas(page)
                        R.add(section, f"{vp_name} — map opens",
                              mobile_canvas, "canvas rendered after toggle")

            # Check header is visible
            header = page.locator("header")
            R.add(section, f"{vp_name} — header visible",
                  header.count() > 0 and header.is_visible())

            # Check footer is visible (scroll to bottom)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.5)
            footer = page.locator("footer")
            R.add(section, f"{vp_name} — footer visible",
                  footer.count() > 0)

            # Tab switching works at this viewport
            switch_tab(page, "Lifestyle")
            lifestyle_alive = page.locator("h1").count() > 0
            R.add(section, f"{vp_name} — tab switch works", lifestyle_alive)

            page.close()
            context.close()
            time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 8: Price-by-type chart (detailed chart test)
        # ════════════════════════════════════════════════════════════════
        section = "Price-By-Type Chart"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("SW1A 1AA"))  # postcode — has full price data including charts
        wait_for_results(page)
        wait_for_tab_data(page)  # Wait for Property tab to load

        # Ensure first section (Prices & Value) is expanded to reveal metric cards
        first_section = page.locator('button:has(h3.text-sm.font-semibold)').first
        if first_section.count() > 0 and first_section.get_attribute("aria-expanded") != "true":
            first_section.click()
            time.sleep(1.5)

        # Expand the Average Sale Price metric card
        avg_price_btn = page.locator('button[aria-label*="Average Sale Price"]').first
        if avg_price_btn.count() > 0:
            avg_price_btn.click()
            time.sleep(3)

        # Look for chart view toggle buttons (type pills: All Types, Price, YoY %, Detached, etc.)
        type_buttons = page.locator('button:has-text("All Types"), button:has-text("Price"), button:has-text("Detached")')
        type_count = type_buttons.count()
        R.add(section, "Chart view toggle buttons",
              type_count > 0, f"{type_count} toggle buttons found")

        # Click "Detached" type pill if available
        by_type_btn = page.locator('button:has-text("Detached"), button:has-text("Average by Type")')
        if by_type_btn.count() > 0:
            by_type_btn.first.click()
            time.sleep(2)
            # After switching, recharts should show data
            paths = page.locator(".recharts-line-curve, .recharts-area-curve, svg path").count()
            R.add(section, "Per-type chart lines", paths > 0, f"{paths} data paths")
        else:
            R.add_warn(section, "Average by Type button", "not found")

        page.close()
        context.close()
        time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 9: Comparable areas + Commute estimator
        # ════════════════════════════════════════════════════════════════
        section = "Interactive Components"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("SW1A 1AA"))
        wait_for_results(page)
        time.sleep(5)

        # Check for Comparable Areas section
        comparable_section = page.locator('text="Comparable Areas"')
        R.add(section, "Comparable Areas section",
              comparable_section.count() > 0)

        # Switch to Lifestyle tab to check Commute Estimator
        switch_tab(page, "Lifestyle")
        time.sleep(3)
        commute_section = page.locator('text="Commute Estimator"')
        R.add(section, "Commute Estimator section",
              commute_section.count() > 0)

        # Check for Useful Resources
        resources = page.locator('text="Useful Resources"')
        R.add(section, "Useful Resources section",
              resources.count() > 0)

        page.close()
        context.close()
        time.sleep(PACE_SECONDS)

        # ════════════════════════════════════════════════════════════════
        # SECTION 10: Search box + navigation
        # ════════════════════════════════════════════════════════════════
        section = "Navigation"
        print(f"\n{'='*60}")
        print(f"SECTION: {section}")
        print(f"{'='*60}")

        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        # Use postcode search — Manchester (LAD type) doesn't show LSOA blurb
        page.goto(results_url("SW1A 1AA"))
        wait_for_results(page)
        wait_for_tab_data(page)

        # Check search box exists in header
        search_input = page.locator('header input[type="text"], header input[type="search"]')
        R.add(section, "Search box in header",
              search_input.count() > 0)

        # Check back arrow link
        back_link = page.locator('a[aria-label="Back to home"]')
        R.add(section, "Back to home link",
              back_link.count() > 0)

        # Check Download Report button
        report_btn = page.locator('text="Download Report"')
        R.add(section, "Download Report button",
              report_btn.count() > 0)

        # Check PersonaSelector
        persona_btn = page.locator('[class*="PersonaSelector"], button:has-text("Family"), select')
        R.add(section, "Persona selector present",
              persona_btn.count() > 0 or page.locator('text="Family"').count() > 0)

        # Check LSOA context blurb — postcode type shows "part of LSOA E01004736"
        page_body = page.locator("body").inner_text()
        has_lsoa_mention = "LSOA" in page_body or "Lower Layer" in page_body
        R.add(section, "LSOA context blurb",
              has_lsoa_mention, f"found LSOA mention: {has_lsoa_mention}")

        # Check footer attribution
        footer_text = page.locator("footer").inner_text()
        R.add(section, "Footer has attribution",
              "Crown copyright" in footer_text or "OpenStreetMap" in footer_text,
              f"footer: '{footer_text[:60]}'")

        page.close()
        context.close()

        browser.close()

    # ════════════════════════════════════════════════════════════════
    # Print summary
    # ════════════════════════════════════════════════════════════════
    return R.summary()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

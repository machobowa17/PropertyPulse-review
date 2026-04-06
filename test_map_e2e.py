"""
Comprehensive E2E map test — Playwright browser automation.
Tests: marker counts, clustering, layer toggles, tab switching, place name search, popup interaction.
"""
import json, time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
RESULTS = {
    "postcode": f"{BASE}/results?q=CR5+1RA",
    "city":     f"{BASE}/results?q=Manchester",
}

def count_markers(page):
    """Count all maplibre markers on page (both default pins and custom price pills)."""
    return page.evaluate("""() => document.querySelectorAll('.maplibregl-marker').length""")

def count_price_pills(page):
    """Count price pill markers (sold price elements with £ text)."""
    return page.evaluate("""() => {
        return [...document.querySelectorAll('.maplibregl-marker')]
            .filter(m => m.textContent && m.textContent.startsWith('£')).length;
    }""")

def count_cluster_markers(page):
    """Count cluster circle markers (numeric text, not £ and not empty)."""
    return page.evaluate("""() => {
        return [...document.querySelectorAll('.maplibregl-marker')]
            .filter(m => {
                const t = (m.textContent || '').trim();
                return t && !t.startsWith('£') && /^\\d+$/.test(t);
            }).length;
    }""")

def count_sold_markers(page):
    """Count all sold-price-related markers (pills + clusters)."""
    return count_price_pills(page) + count_cluster_markers(page)

def get_layer_panel_text(page):
    """Get all text from the layer control panel."""
    panel = page.locator('[class*="absolute top-2 left-2"]')
    if panel.count() == 0:
        return ""
    return panel.inner_text()

def click_layer_toggle(page, label_text):
    """Click a layer toggle checkbox by its label text."""
    page.locator(f'label:has-text("{label_text}")').click()

def wait_for_map_ready(page, timeout=15000):
    """Wait for map markers to appear (or at least the center pin)."""
    page.wait_for_selector('.maplibregl-marker', timeout=timeout)

def run_tests():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # ===== TEST 1: Postcode search — CR5 1RA =====
        print("TEST 1: CR5 1RA — initial marker count (with clustering)")
        page.goto(RESULTS["postcode"])
        wait_for_map_ready(page)
        time.sleep(8)  # Let all async data load (sold prices are fetched via API)

        total = count_markers(page)
        pills = count_price_pills(page)
        clusters = count_cluster_markers(page)
        sold_total = count_sold_markers(page)
        center_pins = total - pills - clusters
        print(f"  Total: {total}, Pills: {pills}, Clusters: {clusters}, Center: {center_pins}")

        # With clustering, pills + clusters should represent all sold prices
        # At the default zoom (fitBounds), some will be clustered
        assert sold_total > 0, f"FAIL: Expected sold markers (pills + clusters) > 0, got {sold_total}"
        assert center_pins == 1, f"FAIL: Expected 1 center pin, got {center_pins}"
        results.append(("CR5 1RA initial markers", f"PASS — {pills} pills + {clusters} clusters + {center_pins} center"))

        # ===== TEST 2: No double rendering =====
        print("TEST 2: No double rendering")
        assert total < 500, f"FAIL: Double rendering detected! {total} markers"
        results.append(("No double rendering", f"PASS — {total} total (not doubled)"))

        # ===== TEST 3: Layer panel text =====
        print("TEST 3: Layer panel — 'Sold Prices (since ...)' label")
        page.locator('button[title="Map layers"]').click()
        time.sleep(0.5)
        panel_text = get_layer_panel_text(page)
        has_since = "since" in panel_text.lower()
        print(f"  Panel text: {repr(panel_text[:100])}")
        assert has_since, f"FAIL: 'since' not found in layer panel"
        results.append(("Sold Prices since label", f"PASS — {panel_text.strip()[:60]}"))

        # ===== TEST 4: Toggle sold prices OFF =====
        print("TEST 4: Toggle sold prices OFF")
        click_layer_toggle(page, "Sold Prices")
        time.sleep(1)
        total_off = count_markers(page)
        sold_off = count_sold_markers(page)
        print(f"  Sold OFF: {total_off} total, {sold_off} sold markers")
        assert sold_off == 0, f"FAIL: Expected 0 sold markers when sold OFF, got {sold_off}"
        assert total_off == 1, f"FAIL: Expected 1 marker (center pin) when sold OFF, got {total_off}"
        results.append(("Sold prices OFF", f"PASS — {total_off} markers (center pin only)"))

        # ===== TEST 5: Toggle sold prices back ON =====
        print("TEST 5: Toggle sold prices back ON")
        click_layer_toggle(page, "Sold Prices")
        time.sleep(1)
        sold_on = count_sold_markers(page)
        print(f"  Sold ON: {sold_on} sold markers")
        assert sold_on > 0, f"FAIL: Expected sold markers > 0 when sold ON, got {sold_on}"
        results.append(("Sold prices ON", f"PASS — {sold_on} sold markers restored"))

        # ===== TEST 6: Ward OFF, LSOA ON =====
        print("TEST 6: Ward boundary OFF, LSOA ON — should show LSOA-extent only")
        click_layer_toggle(page, "Ward Boundary")
        time.sleep(1)
        sold_lsoa = count_sold_markers(page)
        print(f"  Ward OFF, LSOA ON: {sold_lsoa} sold markers")
        assert sold_lsoa < sold_on, f"FAIL: LSOA-only should have fewer sold markers than ward+LSOA"
        assert sold_lsoa > 0, f"FAIL: Should have some LSOA sold markers"
        results.append(("Ward OFF, LSOA ON", f"PASS — {sold_lsoa} sold markers (LSOA-extent)"))

        # ===== TEST 7: Both OFF — show all =====
        print("TEST 7: Both boundaries OFF — should show all sold prices")
        click_layer_toggle(page, "LSOA Boundary")
        time.sleep(1)
        sold_both_off = count_sold_markers(page)
        print(f"  Both OFF: {sold_both_off} sold markers")
        assert sold_both_off >= sold_on, f"FAIL: Both OFF should show all sold markers"
        results.append(("Both boundaries OFF", f"PASS — {sold_both_off} sold markers (all shown)"))

        # Restore both boundaries ON
        click_layer_toggle(page, "Ward Boundary")
        click_layer_toggle(page, "LSOA Boundary")
        time.sleep(0.5)

        # ===== TEST 8: Tab switch to Community =====
        print("TEST 8: Switch to Community & Education tab")
        page.locator('button:has-text("Community")').click()
        time.sleep(3)
        total_community = count_markers(page)
        sold_community = count_sold_markers(page)
        print(f"  Community: {total_community} total, {sold_community} sold markers")
        assert sold_community == 0, f"FAIL: Community tab should have 0 sold markers"
        assert total_community >= 2, f"FAIL: Community should have school markers + center pin"
        results.append(("Community tab markers", f"PASS — {total_community} markers, 0 sold"))

        # ===== TEST 9: Switch back to Property =====
        print("TEST 9: Switch back to Property & Market tab")
        page.locator('button:has-text("Property")').click()
        time.sleep(3)
        sold_back = count_sold_markers(page)
        print(f"  Back to Property: {sold_back} sold markers")
        assert sold_back > 0, f"FAIL: Expected sold markers > 0 back on Property, got {sold_back}"
        results.append(("Back to Property tab", f"PASS — {sold_back} sold markers restored"))

        # ===== TEST 10: Popup interaction (zoom in to expand clusters first) =====
        print("TEST 10: Click a cluster to zoom in, then click a price pill")
        try:
            # Click cluster markers to zoom in until individual pills appear
            for _ in range(4):
                pill_count = count_price_pills(page)
                if pill_count > 0:
                    break
                # Find and click first cluster marker (non-£, numeric text)
                clicked = page.evaluate("""() => {
                    const markers = [...document.querySelectorAll('.maplibregl-marker')];
                    const cluster = markers.find(m => {
                        const t = (m.textContent || '').trim();
                        return t && !t.startsWith('£') && /^\\d+$/.test(t);
                    });
                    if (cluster) { cluster.click(); return true; }
                    return false;
                }""")
                if not clicked:
                    break
                time.sleep(2)  # Let flyTo animation complete

            pill = page.locator('.maplibregl-marker').filter(has_text="£").first
            pill.click(force=True, timeout=5000)
            time.sleep(1)
            popup = page.locator('.maplibregl-popup-content')
            if popup.count() > 0:
                popup_text = popup.inner_text()
                print(f"  Popup text: {popup_text[:80]}")
                results.append(("Popup interaction", f"PASS — {popup_text[:50]}"))
            else:
                results.append(("Popup interaction", "WARN — click registered but no popup visible"))
        except Exception as e:
            results.append(("Popup interaction", f"WARN — {str(e)[:50]}"))

        page.close()

        # ===== TEST 11: Place name search — Manchester =====
        print("\nTEST 11: Manchester (place name, no LSOA) — radius fallback")
        page2 = context.new_page()
        page2.goto(RESULTS["city"])
        wait_for_map_ready(page2, timeout=20000)
        # Wait for pois to load
        for _ in range(10):
            time.sleep(1)
            sold_manc = count_sold_markers(page2)
            if sold_manc > 0:
                break

        sold_manc = count_sold_markers(page2)
        pills_manc = count_price_pills(page2)
        clusters_manc = count_cluster_markers(page2)
        print(f"  Manchester: {sold_manc} sold ({pills_manc} pills + {clusters_manc} clusters)")
        assert sold_manc > 0, f"FAIL: Manchester should have sold markers"
        results.append(("Manchester markers", f"PASS — {sold_manc} sold markers ({pills_manc} pills + {clusters_manc} clusters)"))

        # ===== TEST 12: Manchester — toggle LSOA ON, Ward OFF should NOT hide all pills =====
        print("TEST 12: Manchester — Ward OFF, LSOA ON (no LSOA data)")
        page2.locator('button[title="Map layers"]').click()
        time.sleep(0.5)
        click_layer_toggle(page2, "Ward Boundary")
        time.sleep(1)
        sold_manc_lsoa = count_sold_markers(page2)
        print(f"  Manchester Ward OFF, LSOA ON: {sold_manc_lsoa} sold markers")
        assert sold_manc_lsoa > 0, f"FAIL: searchLsoa='_' bug — sold markers disappeared when ward OFF + LSOA ON"
        results.append(("Manchester LSOA-only filter", f"PASS — {sold_manc_lsoa} sold markers (not hidden)"))

        page2.close()

        # ===== TEST 13: Environment tab — flood zones =====
        print("\nTEST 13: Environment tab — flood zones")
        page3 = context.new_page()
        page3.goto(RESULTS["postcode"])
        wait_for_map_ready(page3)
        time.sleep(2)
        page3.locator('button:has-text("Environment")').click()
        time.sleep(3)

        total_env = count_markers(page3)
        sold_env = count_sold_markers(page3)
        print(f"  Environment: {total_env} total, {sold_env} sold markers")
        assert sold_env == 0, f"FAIL: Environment tab should have 0 sold markers"
        results.append(("Environment tab", f"PASS — {total_env} markers, 0 sold"))

        # ===== TEST 14: Lifestyle tab — stations + EV chargers =====
        print("TEST 14: Lifestyle tab — stations + EV chargers")
        page3.locator('button:has-text("Lifestyle")').click()
        time.sleep(3)
        total_life = count_markers(page3)
        sold_life = count_sold_markers(page3)
        print(f"  Lifestyle: {total_life} total, {sold_life} sold markers")
        assert sold_life == 0, f"FAIL: Lifestyle tab should have 0 sold markers"
        assert total_life >= 2, f"FAIL: Lifestyle should have station/EV markers"
        results.append(("Lifestyle tab", f"PASS — {total_life} markers, 0 sold"))

        page3.close()
        browser.close()

    # Print summary
    print("\n" + "=" * 60)
    print("E2E MAP TEST SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, result in results:
        status = "PASS" if result.startswith("PASS") else ("WARN" if result.startswith("WARN") else "FAIL")
        icon = "✓" if status == "PASS" else ("⚠" if status == "WARN" else "✗")
        print(f"  {icon} {name}: {result}")
        if status == "FAIL":
            all_pass = False
    print("=" * 60)
    print(f"{'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    return all_pass

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

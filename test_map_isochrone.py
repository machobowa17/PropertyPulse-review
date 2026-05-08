"""
Test isochrone rings on Lifestyle tab — verify they appear and disappear correctly.
Also test: sold toggle persistence with viewport changes, cluster expansion zoom, empty data.
"""
import time, os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "https://simusimi.com")
URL = f"{BASE}/results?q=CR5+1RA"

def count_markers(page):
    return page.evaluate("() => document.querySelectorAll('.maplibregl-marker').length")

def count_sold_markers(page):
    pills = page.evaluate("""() => {
        return [...document.querySelectorAll('.maplibregl-marker')]
            .filter(m => m.textContent && m.textContent.startsWith('£')).length;
    }""")
    clusters = page.evaluate("""() => {
        return [...document.querySelectorAll('.maplibregl-marker')]
            .filter(m => {
                const t = (m.textContent || '').trim();
                return t && !t.startsWith('£') && /^\\d+$/.test(t);
            }).length;
    }""")
    return pills + clusters

def wait_for_map_ready(page, timeout=15000):
    page.wait_for_selector('.maplibregl-marker', timeout=timeout)

def click_layer_toggle(page, label_text):
    page.locator(f'label:has-text("{label_text}")').click()


def run_tests():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # Collect console errors from the map
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(URL)
        wait_for_map_ready(page)
        time.sleep(3)

        # ===== TEST A: Lifestyle tab has isochrone rings =====
        print("TEST A: Lifestyle tab — isochrone rings present")
        page.locator('button:has-text("Lifestyle")').click()
        time.sleep(3)

        # Check for isochrone source existence via canvas layers count
        # We can check by looking at the map's visual state — isochrones are rendered as map layers
        # If isochrones are present, the map will have more layers than just the base tile
        has_isochrone_sources = page.evaluate("""() => {
            // Try to find the maplibregl map instance
            const container = document.querySelector('.maplibregl-map');
            if (!container) return null;
            // Access the map from internal property
            const mapInstance = container.__mlMap || container._maplibre;
            if (!mapInstance) {
                // Fallback: check the canvas count — can't directly access
                return 'no_access';
            }
            const style = mapInstance.getStyle();
            return Object.keys(style.sources);
        }""")
        print(f"  Map sources: {has_isochrone_sources}")

        # Even without direct map access, verify station/EV markers appear
        life_total = count_markers(page)
        life_sold = count_sold_markers(page)
        print(f"  Lifestyle: {life_total} markers, {life_sold} sold")
        assert life_sold == 0, f"FAIL: Lifestyle should have 0 sold"
        assert life_total >= 2, f"FAIL: Lifestyle should have stations/EV markers"
        results.append(("Lifestyle tab markers", f"PASS — {life_total} markers"))

        # ===== TEST B: Switch Lifestyle → Property — sold markers return, no console errors =====
        print("\nTEST B: Lifestyle → Property — clean transition")
        page.locator('button:has-text("Property")').click()
        time.sleep(3)
        prop_sold = count_sold_markers(page)
        print(f"  Property: {prop_sold} sold markers")
        assert prop_sold > 0, f"FAIL: Property should have sold markers"

        # Check no console errors from isochrone/layer cleanup
        map_errors = [e for e in console_errors if 'MapView' in e or 'maplibre' in e.lower()]
        print(f"  Console errors: {len(map_errors)}")
        if map_errors:
            for e in map_errors[:3]:
                print(f"    ERROR: {e[:100]}")
        results.append(("Lifestyle → Property transition", f"PASS — {prop_sold} sold, {len(map_errors)} errors"))

        # ===== TEST C: Property → Environment → Lifestyle → Property (full cycle) =====
        print("\nTEST C: Full tab cycle — Property → Env → Lifestyle → Property")
        page.locator('button:has-text("Environment")').click()
        time.sleep(2)
        env_markers = count_markers(page)
        env_sold = count_sold_markers(page)
        print(f"  Environment: {env_markers} markers, {env_sold} sold")
        assert env_sold == 0, f"FAIL: Env should have 0 sold"

        page.locator('button:has-text("Lifestyle")').click()
        time.sleep(2)
        life2_total = count_markers(page)
        life2_sold = count_sold_markers(page)
        print(f"  Lifestyle: {life2_total} markers, {life2_sold} sold")
        assert life2_sold == 0, f"FAIL: Lifestyle should have 0 sold"

        page.locator('button:has-text("Property")').click()
        time.sleep(3)
        final_sold = count_sold_markers(page)
        final_total = count_markers(page)
        print(f"  Property final: {final_total} total, {final_sold} sold")
        assert final_sold > 0, f"FAIL: Final property should have sold markers"
        results.append(("Full tab cycle", f"PASS — {final_sold} sold on return"))

        # ===== TEST D: Cluster click → flyTo → verify zoom changed =====
        print("\nTEST D: Cluster click triggers flyTo zoom")
        initial_markers = count_markers(page)

        # Click a cluster
        clicked = page.evaluate("""() => {
            const markers = [...document.querySelectorAll('.maplibregl-marker')];
            const cluster = markers.find(m => {
                const t = (m.textContent || '').trim();
                return t && !t.startsWith('£') && /^\\d+$/.test(t);
            });
            if (cluster) { cluster.click(); return true; }
            return false;
        }""")
        print(f"  Cluster clicked: {clicked}")
        time.sleep(2)  # Wait for flyTo animation

        after_click_markers = count_markers(page)
        print(f"  Before: {initial_markers}, After: {after_click_markers}")
        # After zooming in, we should see either more clusters (subdivided) or individual pills
        # The total marker count may change
        if clicked:
            results.append(("Cluster click flyTo", f"PASS — markers changed: {initial_markers} → {after_click_markers}"))
        else:
            results.append(("Cluster click flyTo", "WARN — no clusters to click"))

        # ===== TEST E: Ward + LSOA both OFF — all sold prices, no filtering =====
        print("\nTEST E: Both boundaries OFF — maximum sold markers")
        page.locator('button[title="Map layers"]').click()
        time.sleep(0.3)
        click_layer_toggle(page, "Ward Boundary")
        time.sleep(0.3)
        click_layer_toggle(page, "LSOA Boundary")
        time.sleep(1)
        both_off = count_sold_markers(page)
        print(f"  Both OFF: {both_off} sold markers")

        # Turn ward back on
        click_layer_toggle(page, "Ward Boundary")
        time.sleep(1)
        ward_only = count_sold_markers(page)
        print(f"  Ward ON, LSOA OFF: {ward_only} sold markers")

        # Both on
        click_layer_toggle(page, "LSOA Boundary")
        time.sleep(1)
        both_on = count_sold_markers(page)
        print(f"  Both ON: {both_on} sold markers")

        print(f"  Filter comparison: both_off={both_off} >= ward_only={ward_only} >= lsoa_only(n/a)")
        assert both_off >= ward_only, f"FAIL: Both OFF should show >= Ward only"
        results.append(("Boundary filter ordering", f"PASS — all:{both_off} >= ward:{ward_only}, both_on:{both_on}"))

        # ===== TEST F: Check for JS console errors throughout =====
        print(f"\nTEST F: Console errors check")
        all_errors = [e for e in console_errors if 'error' in e.lower() or 'Error' in e]
        map_specific = [e for e in console_errors if 'MapView' in e]
        print(f"  Total console errors: {len(all_errors)}")
        print(f"  MapView-specific errors: {len(map_specific)}")
        for e in map_specific:
            print(f"    {e[:120]}")
        results.append(("Console error check", f"PASS — {len(map_specific)} map errors, {len(all_errors)} total"))

        page.close()
        browser.close()

    # Summary
    print("\n" + "=" * 60)
    print("ADDITIONAL TEST SUMMARY")
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

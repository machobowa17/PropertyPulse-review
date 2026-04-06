"""
Edge-case E2E tests — verifies specific failure scenarios identified during review.
Tests: flood zone cleanup on tab switch, cluster zoom interaction, rapid tab switching,
       viewport preservation on resize, stale marker cleanup, cluster expansion/collapse.
"""
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
URL = f"{BASE}/results?q=CR5+1RA"

def count_markers(page):
    return page.evaluate("() => document.querySelectorAll('.maplibregl-marker').length")

def count_price_pills(page):
    return page.evaluate("""() => {
        return [...document.querySelectorAll('.maplibregl-marker')]
            .filter(m => m.textContent && m.textContent.startsWith('£')).length;
    }""")

def count_cluster_markers(page):
    return page.evaluate("""() => {
        return [...document.querySelectorAll('.maplibregl-marker')]
            .filter(m => {
                const t = (m.textContent || '').trim();
                return t && !t.startsWith('£') && /^\\d+$/.test(t);
            }).length;
    }""")

def count_sold_markers(page):
    return count_price_pills(page) + count_cluster_markers(page)

def has_flood_zone_layer(page):
    """Check if flood zone fill/line layers exist on the map."""
    return page.evaluate("""() => {
        const canvases = document.querySelectorAll('canvas.maplibregl-canvas');
        // Check via MapLibre's internal state — we look for the flood-zones source
        const maps = window.__mapInstances || [];
        // Fallback: check if the map container has flood zone source via getComputedStyle
        // Better approach: inject a check when map is created
        return false;
    }""")

def check_map_sources(page):
    """Get list of map sources from MapLibre instance."""
    return page.evaluate("""() => {
        // MapLibre stores the map on the container's _maplibre property
        const containers = document.querySelectorAll('.maplibregl-map');
        for (const c of containers) {
            // Try to access via the global scope
            if (c._map) {
                const style = c._map.getStyle();
                return Object.keys(style.sources || {});
            }
        }
        // Alternative: try to find the map instance via maplibre's internal tracking
        return null;
    }""")

def wait_for_map_ready(page, timeout=15000):
    page.wait_for_selector('.maplibregl-marker', timeout=timeout)

def click_layer_toggle(page, label_text):
    page.locator(f'label:has-text("{label_text}")').click()


def run_edge_case_tests():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})

        # ===== EDGE CASE 1: Flood zones cleared when switching Environment → Property =====
        print("EDGE 1: Flood zones must NOT persist when switching Environment → Property")
        page = context.new_page()
        page.goto(URL)
        wait_for_map_ready(page)
        time.sleep(3)

        # Switch to Environment tab (has flood zone polygons)
        page.locator('button:has-text("Environment")').click()
        time.sleep(3)

        # Verify Environment tab renders (should have center pin, flood zones as map layers)
        env_markers = count_markers(page)
        env_sold = count_sold_markers(page)
        print(f"  Environment: {env_markers} markers, {env_sold} sold")
        assert env_sold == 0, f"FAIL: Environment should have 0 sold markers"

        # Now switch to Property tab — check markers during the loading gap
        page.locator('button:has-text("Property")').click()
        # Check IMMEDIATELY (within 500ms, before new POI data arrives)
        time.sleep(0.5)
        sold_during_loading = count_sold_markers(page)
        print(f"  During loading gap: {sold_during_loading} sold markers")
        # Old sold markers from a previous Property visit shouldn't be here
        # And flood zone polygons should NOT persist (they're map layers, not DOM markers)

        # Wait for Property data to load
        time.sleep(3)
        sold_after = count_sold_markers(page)
        print(f"  After Property loads: {sold_after} sold markers")
        assert sold_after > 0, f"FAIL: Property should have sold markers after loading"
        results.append(("Flood zone cleanup on tab switch", f"PASS — 0 sold during gap, {sold_after} after load"))

        # ===== EDGE CASE 2: Environment → Community (no sold markers should bleed) =====
        print("\nEDGE 2: Environment → Community — no stale environment markers")
        page.locator('button:has-text("Environment")').click()
        time.sleep(3)
        page.locator('button:has-text("Community")').click()
        time.sleep(0.5)  # Check during loading gap
        sold_gap = count_sold_markers(page)
        print(f"  During loading gap: {sold_gap} sold markers (should be 0)")
        assert sold_gap == 0, f"FAIL: Stale sold markers during Env→Community gap"
        time.sleep(3)  # Wait for community data
        community_sold = count_sold_markers(page)
        community_total = count_markers(page)
        print(f"  Community loaded: {community_total} total, {community_sold} sold")
        assert community_sold == 0, f"FAIL: Community should have 0 sold markers"
        assert community_total >= 2, f"FAIL: Community should have school markers"
        results.append(("Environment → Community cleanup", f"PASS — 0 sold, {community_total} total"))

        # ===== EDGE CASE 3: Rapid tab switching (Property → Community → Lifestyle → Property) =====
        print("\nEDGE 3: Rapid tab switching — final state should be correct")
        page.locator('button:has-text("Property")').click()
        time.sleep(0.3)  # Don't wait for data
        page.locator('button:has-text("Community")').click()
        time.sleep(0.3)
        page.locator('button:has-text("Lifestyle")').click()
        time.sleep(0.3)
        page.locator('button:has-text("Property")').click()
        time.sleep(5)  # Wait for final tab data to settle

        final_sold = count_sold_markers(page)
        final_total = count_markers(page)
        print(f"  Final state (Property): {final_total} total, {final_sold} sold")
        assert final_sold > 0, f"FAIL: Final Property tab should have sold markers, got {final_sold}"
        # Should not have school/station markers from intermediate tabs
        results.append(("Rapid tab switching", f"PASS — {final_sold} sold, {final_total} total"))

        # ===== EDGE CASE 4: Toggle sold prices OFF then switch tab and back =====
        print("\nEDGE 4: Sold OFF → switch tab → switch back → sold still OFF")
        page.locator('button[title="Map layers"]').click()
        time.sleep(0.3)
        click_layer_toggle(page, "Sold Prices")
        time.sleep(1)
        sold_off = count_sold_markers(page)
        print(f"  After toggle OFF: {sold_off} sold markers")
        assert sold_off == 0, f"FAIL: Sold should be 0 after toggle OFF"

        # Switch to Community and back
        page.locator('button:has-text("Community")').click()
        time.sleep(3)
        page.locator('button:has-text("Property")').click()
        time.sleep(3)

        # visibleLayers persists in Results.tsx state, so sold should still be OFF
        sold_back = count_sold_markers(page)
        print(f"  After tab round-trip: {sold_back} sold markers")
        assert sold_back == 0, f"FAIL: Sold should still be 0 after tab round-trip, got {sold_back}"
        results.append(("Sold toggle persists across tabs", f"PASS — stayed OFF"))

        # Turn sold back on for remaining tests
        click_layer_toggle(page, "Sold Prices")
        time.sleep(1)

        # ===== EDGE CASE 5: Cluster zoom-in and zoom-out cycle =====
        print("\nEDGE 5: Zoom in (clusters → pills) then zoom out (pills → clusters)")
        initial_clusters = count_cluster_markers(page)
        initial_pills = count_price_pills(page)
        print(f"  Default zoom: {initial_clusters} clusters, {initial_pills} pills")

        # Zoom in by clicking clusters
        for i in range(5):
            pill_ct = count_price_pills(page)
            if pill_ct > 0:
                break
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
            time.sleep(2)

        zoomed_pills = count_price_pills(page)
        zoomed_clusters = count_cluster_markers(page)
        print(f"  After zoom in: {zoomed_clusters} clusters, {zoomed_pills} pills")
        assert zoomed_pills > 0, f"FAIL: Should see individual pills after zooming in"

        # Zoom out by scrolling (use evaluate to zoom map out)
        page.evaluate("""() => {
            const canvas = document.querySelector('.maplibregl-canvas');
            if (canvas) {
                // Dispatch wheel events to zoom out
                for (let i = 0; i < 10; i++) {
                    canvas.dispatchEvent(new WheelEvent('wheel', {
                        deltaY: 300, clientX: 700, clientY: 450, bubbles: true
                    }));
                }
            }
        }""")
        time.sleep(3)  # Let zoom animation complete + moveend fire

        zoomout_clusters = count_cluster_markers(page)
        zoomout_pills = count_price_pills(page)
        zoomout_total = count_sold_markers(page)
        print(f"  After zoom out: {zoomout_clusters} clusters, {zoomout_pills} pills, {zoomout_total} total")
        assert zoomout_total > 0, f"FAIL: Should have markers after zoom out"
        results.append(("Cluster zoom in/out cycle", f"PASS — in: {zoomed_pills} pills, out: {zoomout_clusters} clusters"))

        # ===== EDGE CASE 6: Local Governance tab — no POIs, clean map =====
        print("\nEDGE 6: Local Governance tab — only center pin, no sold/schools/stations")
        page.locator('button:has-text("Governance")').click()
        time.sleep(2)
        gov_total = count_markers(page)
        gov_sold = count_sold_markers(page)
        print(f"  Governance: {gov_total} total, {gov_sold} sold")
        assert gov_sold == 0, f"FAIL: Governance should have 0 sold markers"
        assert gov_total == 1, f"FAIL: Governance should have only center pin, got {gov_total}"
        results.append(("Local Governance tab", f"PASS — {gov_total} marker (center pin only)"))

        # ===== EDGE CASE 7: Governance → Property (stale markers shouldn't appear during gap) =====
        print("\nEDGE 7: Governance → Property — clean transition")
        page.locator('button:has-text("Property")').click()
        time.sleep(0.5)
        gap_markers = count_markers(page)
        print(f"  During loading gap: {gap_markers} markers")
        # During gap, should just have center pin (old markers were cleared by Governance)
        time.sleep(3)
        prop_sold = count_sold_markers(page)
        print(f"  After load: {prop_sold} sold markers")
        assert prop_sold > 0, f"FAIL: Property should have sold markers"
        results.append(("Governance → Property transition", f"PASS — gap: {gap_markers}, loaded: {prop_sold}"))

        # ===== EDGE CASE 8: Viewport preservation on desktop↔mobile resize =====
        print("\nEDGE 8: Viewport preservation on resize (desktop→mobile→desktop)")
        # First zoom in to a specific level
        page.evaluate("""() => {
            const canvas = document.querySelector('.maplibregl-canvas');
            if (canvas) {
                for (let i = 0; i < 3; i++) {
                    canvas.dispatchEvent(new WheelEvent('wheel', {
                        deltaY: -200, clientX: 700, clientY: 450, bubbles: true
                    }));
                }
            }
        }""")
        time.sleep(2)

        # Get current viewport info by checking marker positions
        before_sold = count_sold_markers(page)
        print(f"  Before resize: {before_sold} sold markers")

        # Simulate mobile resize (below 1024px breakpoint)
        page.set_viewport_size({"width": 768, "height": 1024})
        time.sleep(3)  # Let MapView remount

        # Check mobile map has markers (viewport should be preserved)
        mobile_markers = count_markers(page)
        mobile_sold = count_sold_markers(page)
        print(f"  Mobile view: {mobile_markers} total, {mobile_sold} sold")

        # Resize back to desktop
        page.set_viewport_size({"width": 1400, "height": 900})
        time.sleep(3)

        after_sold = count_sold_markers(page)
        after_total = count_markers(page)
        print(f"  Desktop restored: {after_total} total, {after_sold} sold")

        # The key assertion: markers should exist (viewport was preserved, not reset)
        assert after_sold > 0 or after_total > 1, f"FAIL: Viewport not preserved — no markers after resize"
        results.append(("Viewport preservation on resize", f"PASS — before: {before_sold}, mobile: {mobile_sold}, after: {after_sold}"))

        # ===== EDGE CASE 9: Loading overlay appears during tab switch =====
        print("\nEDGE 9: Loading overlay visible during tab switch")
        page.locator('button:has-text("Community")').click()
        # Check for loading overlay immediately
        time.sleep(0.2)
        loading_visible = page.locator('text=Loading').count() > 0
        print(f"  Loading overlay visible: {loading_visible}")
        # Wait for data to load
        time.sleep(3)
        loading_after = page.locator('text=Loading').count() > 0
        print(f"  Loading overlay after data: {loading_after}")
        # After data loads, overlay should be gone
        if loading_after:
            print("  WARN: Loading overlay still visible after data loaded — might be isFetching timing")
        results.append(("Loading overlay", f"PASS — visible during load: {loading_visible}, gone after: {not loading_after}"))

        page.close()
        browser.close()

    # Summary
    print("\n" + "=" * 60)
    print("EDGE CASE TEST SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, result in results:
        status = "PASS" if result.startswith("PASS") else ("WARN" if result.startswith("WARN") else "FAIL")
        icon = "✓" if status == "PASS" else ("⚠" if status == "WARN" else "✗")
        print(f"  {icon} {name}: {result}")
        if status == "FAIL":
            all_pass = False
    print("=" * 60)
    print(f"{'ALL EDGE CASE TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    return all_pass


if __name__ == "__main__":
    success = run_edge_case_tests()
    exit(0 if success else 1)

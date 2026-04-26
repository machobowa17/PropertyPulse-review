"""
E2E test: Verify travel module data flows from DB → API → Frontend.

Usage: python3 test_travel_data_e2e.py
"""
import sys
import traceback
from playwright.sync_api import sync_playwright

BASE = "https://simusimi.com"
TIMEOUT = 30_000
PASS = 0
FAIL = 0
ERRORS = []


def _log(status, name, detail=""):
    global PASS, FAIL
    if status == "PASS":
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  ✗ {name} — {detail}")


def _search_and_expand_stations(page, postcode):
    """Search postcode, go to Lifestyle tab, expand the station metric card."""
    page.goto(BASE, timeout=TIMEOUT)
    page.wait_for_load_state("networkidle", timeout=TIMEOUT)

    search_input = page.locator("input[type='text']").first
    search_input.fill(postcode)
    search_input.press("Enter")

    page.wait_for_url("**/results**", timeout=TIMEOUT)
    page.wait_for_load_state("networkidle", timeout=TIMEOUT)

    # Click Lifestyle tab
    page.locator("text=Lifestyle").first.click()
    page.wait_for_timeout(3000)

    # The MetricCard for stations is lazy-mounted. We need to find it and click to expand.
    # MetricCards have a click handler on the header area. Look for "Nearest Station" or
    # "Rail/Metro" in the collapsed metric card summary.
    # Try clicking the metric text directly.
    station_metric = page.locator("text=/Nearest Station|Rail.*Metro.*Stations/").first
    station_metric.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    # Use JS click to bypass any overlay/visibility issues
    station_metric.evaluate("el => el.click()")
    page.wait_for_timeout(3000)

    # The StationTable should now be mounted. Scroll down to see it.
    # The table is inside the expanded metric card
    table = page.locator("table").filter(has=page.locator("th:has-text('Name')"))
    if table.count() > 0:
        table.first.scroll_into_view_if_needed()
        page.wait_for_timeout(500)


def test_london_fares_and_travelcard(page):
    """CR5 2JP — fares, travelcard badge, season ticket, journey legs."""
    print("\n[1] London (CR5 2JP) — fares + travelcard + legs")
    _search_and_expand_stations(page, "CR5 2JP")

    # Check Rail tab button exists in DOM
    rail_tab = page.locator("button:has-text('National Rail')")
    if rail_tab.count() > 0:
        _log("PASS", "Rail tab in DOM")
    else:
        _log("FAIL", "Rail tab in DOM", "Not found")
        page.screenshot(path="test-results/travel_london_debug.png", full_page=True)
        return

    # Expand Coulsdon South
    cds_row = page.locator("tr:has-text('Coulsdon South')")
    if cds_row.count() == 0:
        # Maybe not rail tab - check what tab is active
        page.screenshot(path="test-results/travel_london_no_cds.png", full_page=True)
        _log("FAIL", "Coulsdon South row", "Not found")
        return
    _log("PASS", "Coulsdon South row found")

    # JS click to bypass overflow-hidden
    cds_row.first.evaluate("el => el.click()")
    page.wait_for_timeout(3000)

    # Now check for destination content in the DOM (may not be visually scrolled to)
    dest_header = page.locator("text=Top destinations from Coulsdon South")
    if dest_header.count() > 0:
        _log("PASS", "Destination panel rendered")
        dest_header.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
    else:
        _log("FAIL", "Destination panel", "Not rendered after click")
        page.screenshot(path="test-results/travel_london_no_dest.png", full_page=True)
        return

    # Check fare texts exist in DOM (don't require visibility)
    peak = page.locator("text=/Peak £\\d+\\.\\d{2}/")
    if peak.count() > 0:
        _log("PASS", f"Peak fare rendered ({peak.first.text_content().strip()})")
    else:
        _log("FAIL", "Peak fare", "No 'Peak £X.XX' in DOM")

    offpeak = page.locator("text=/Off-peak £\\d+\\.\\d{2}/")
    if offpeak.count() > 0:
        _log("PASS", f"Off-peak fare rendered ({offpeak.first.text_content().strip()})")
    else:
        _log("FAIL", "Off-peak fare", "No 'Off-peak £X.XX' in DOM")

    season = page.locator("text=/£[\\d,]+\\/yr/")
    if season.count() > 0:
        _log("PASS", f"Season ticket rendered ({season.first.text_content().strip()})")
    else:
        _log("FAIL", "Season ticket", "No '£X,XXX/yr' in DOM")

    tc = page.locator("text=Travelcard")
    if tc.count() > 0:
        _log("PASS", "Travelcard label rendered")
    else:
        _log("FAIL", "Travelcard label", "Not in DOM")

    zone = page.locator("text=/Z\\d+-?\\d*/")
    if zone.count() > 0:
        _log("PASS", f"Zone badge rendered ({zone.first.text_content().strip()})")
    else:
        _log("FAIL", "Zone badge", "Not in DOM")

    jtime = page.locator("text=/\\d+ min/")
    if jtime.count() > 0:
        _log("PASS", "Journey time rendered")
    else:
        _log("FAIL", "Journey time", "Not in DOM")

    # Click LBG journey card to expand legs
    lbg = page.locator("button:has-text('London Bridge')")
    if lbg.count() > 0:
        lbg.first.evaluate("el => el.click()")
        page.wait_for_timeout(2000)

        walk = page.locator("text=/Walk/")
        if walk.count() > 0:
            _log("PASS", "Walking leg rendered")
        else:
            _log("FAIL", "Walking leg", "Not rendered")

        tl = page.locator("text=Thameslink")
        if tl.count() > 0:
            _log("PASS", "Thameslink line rendered")
        else:
            _log("FAIL", "Thameslink line", "Not rendered")

    time_input = page.locator("input[type='time']")
    if time_input.count() > 0:
        _log("PASS", "Time selector rendered")
    else:
        _log("FAIL", "Time selector", "Not in DOM")

    search = page.locator("input[placeholder='Search another destination...']")
    if search.count() > 0:
        _log("PASS", "Custom search rendered")
    else:
        _log("FAIL", "Custom search", "Not in DOM")

    page.screenshot(path="test-results/travel_london.png", full_page=True)


def test_station_enrichment(page):
    """CR5 2JP — operator, zone column, step-free icon."""
    print("\n[2] Station enrichment columns")
    _search_and_expand_stations(page, "CR5 2JP")

    for check, selector in [
        ("Operator (Southern)", "td:has-text('Southern')"),
        ("Zone column header", "th:has-text('Zone')"),
        ("CRS code (CDS)", "text=(CDS)"),
        ("Step-free icon", "[title='Step-free access']"),
    ]:
        el = page.locator(selector)
        if el.count() > 0:
            _log("PASS", check)
        else:
            _log("FAIL", check, "Not found")

    page.screenshot(path="test-results/travel_enrichment.png", full_page=True)


def test_manchester(page):
    """M60 7RA — fares but no travelcard for non-London."""
    print("\n[3] Manchester (M60 7RA) — fares, no travelcard")
    _search_and_expand_stations(page, "M60 7RA")

    man_row = page.locator("tr:has-text('Manchester Piccadilly')")
    if man_row.count() == 0:
        _log("FAIL", "Manchester Piccadilly", "Not found")
        page.screenshot(path="test-results/travel_manchester_debug.png", full_page=True)
        return
    _log("PASS", "Manchester Piccadilly found")

    man_row.first.evaluate("el => el.click()")
    page.wait_for_timeout(3000)

    peak = page.locator("text=/Peak £\\d+\\.\\d{2}/")
    if peak.count() > 0:
        _log("PASS", f"Manchester peak fare ({peak.first.text_content().strip()})")
    else:
        _log("FAIL", "Manchester peak fare", "Not rendered")

    tc = page.locator("text=Travelcard")
    if tc.count() == 0:
        _log("PASS", "No travelcard (correct)")
    else:
        _log("FAIL", "Unexpected travelcard", "Found in Manchester")

    page.screenshot(path="test-results/travel_manchester.png", full_page=True)


def test_rural(page):
    """TA24 8SH — bus-only, no rail, graceful handling."""
    print("\n[4] Rural (TA24 8SH) — bus-only")
    _search_and_expand_stations(page, "TA24 8SH")

    bus_tab = page.locator("button:has-text('Bus')")
    if bus_tab.count() > 0:
        _log("PASS", "Bus tab found")
    else:
        _log("FAIL", "Bus tab", "Not found")

    rail_tab = page.locator("button:has-text('National Rail')")
    if rail_tab.count() == 0:
        _log("PASS", "No rail tab (correct)")
    else:
        _log("FAIL", "Unexpected rail tab", "Found in rural area")

    dest = page.locator("text=/Top destinations from/")
    if dest.count() == 0:
        _log("PASS", "No destination panel (correct)")
    else:
        _log("FAIL", "Unexpected destinations", "Found for bus stops")

    page.screenshot(path="test-results/travel_rural.png", full_page=True)


def main():
    global PASS, FAIL
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})

        tests = [
            test_london_fares_and_travelcard,
            test_station_enrichment,
            test_manchester,
            test_rural,
        ]

        for test_fn in tests:
            page = context.new_page()
            try:
                test_fn(page)
            except Exception as e:
                FAIL += 1
                ERRORS.append(f"{test_fn.__name__}: CRASH — {e}")
                print(f"  ✗ CRASH: {e}")
                traceback.print_exc()
            finally:
                page.close()

        browser.close()

    print(f"\n{'='*60}")
    print(f"Travel Data E2E: {PASS} passed, {FAIL} failed")
    if ERRORS:
        print("\nFailures:")
        for e in ERRORS:
            print(f"  ✗ {e}")
    print(f"{'='*60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

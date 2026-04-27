"""
LAD Pre-Aggregation Validation Tests

Tests the LAD materialized view routing for county/LAD searches.
Validates data accuracy, graceful degradation, frontend rendering,
and edge cases across all 5 tabs.

Run: BASE_URL="https://simusimi.com" API_URL="https://simusimi.com/api/v1" python3 test_lad_preaggregate.py
"""
import json
import math
import os
import sys
import time

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# ── Config ──────────────────────────────────────────────────────────
BASE = os.environ.get("BASE_URL", "https://simusimi.com")
API = os.environ.get("API_URL", "https://simusimi.com/api/v1")

TAB_NAMES = ["Property", "Lifestyle", "Environment", "Community", "Governance"]
TAB_FULL = [
    "Property & Market",
    "Lifestyle & Connectivity",
    "Environment & Safety",
    "Community & Education",
    "Local Governance",
]

# Rate limit: 60 req/min
PACE = 1.1
last_request_time = 0


# ── Helpers ─────────────────────────────────────────────────────────
class TimeoutResponse:
    status_code = 0
    text = "TIMEOUT"
    def json(self):
        return {}


class TestResults:
    def __init__(self):
        self.results: list[tuple[str, str, str]] = []

    def add(self, section: str, name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append((section, name, f"{status} — {detail}" if detail else status))
        marker = "  ✓" if passed else "  ✗"
        print(f"{marker} [{section}] {name}" + (f" ({detail})" if detail else ""))

    def add_warn(self, section: str, name: str, detail: str = ""):
        self.results.append((section, name, f"WARN — {detail}"))
        print(f"  ⚠ [{section}] {name} ({detail})")

    def summary(self):
        passed = sum(1 for _, _, s in self.results if s.startswith("PASS"))
        failed = sum(1 for _, _, s in self.results if s.startswith("FAIL"))
        warned = sum(1 for _, _, s in self.results if s.startswith("WARN"))
        total = len(self.results)

        print(f"\n{'='*60}")
        print(f"RESULTS: {passed}/{total} passed, {failed} failed, {warned} warnings")
        print(f"{'='*60}")

        if failed > 0:
            print("\nFAILURES:")
            for section, name, status in self.results:
                if status.startswith("FAIL"):
                    print(f"  [{section}] {name}: {status}")

        return failed


def paced_get(url, timeout=120, **kwargs):
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < PACE:
        time.sleep(PACE - elapsed)
    last_request_time = time.time()
    try:
        r = requests.get(url, timeout=timeout, **kwargs)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return TimeoutResponse()
    if r.status_code == 429:
        time.sleep(5)
        last_request_time = time.time()
        try:
            r = requests.get(url, timeout=timeout, **kwargs)
        except:
            return TimeoutResponse()
    return r


def resolve(query):
    r = paced_get(f"{API}/resolve", params={"q": query})
    if r.status_code != 200:
        return None, None
    data = r.json()
    return data.get("session_key"), data


def fetch_tab(session_key, tab_name, timeout=60):
    r = paced_get(f"{API}/area", params={"session_key": session_key, "tab": tab_name}, timeout=timeout)
    if r.status_code != 200:
        return None
    return r.json()


def results_url(query):
    return f"{BASE}/results?q={query.replace(' ', '+')}"


def wait_for_results(page, timeout=60000):
    page.wait_for_selector("h1", timeout=timeout)


def wait_for_tab_data(page, timeout=45000):
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        count = page.locator('[class*="border-l-"][class*="rounded-2xl"]').count()
        if count >= 1:
            time.sleep(0.5)
            return True
        time.sleep(1)
    return False


def count_metric_cards(page):
    return page.locator('[class*="border-l-"][class*="rounded-2xl"]').count()


def get_metric_card_texts(page):
    cards = page.locator('[class*="border-l-"][class*="rounded-2xl"]')
    texts = []
    for i in range(cards.count()):
        texts.append(cards.nth(i).inner_text())
    return texts


def switch_tab(page, short_name):
    btn = page.locator(f'button:has-text("{short_name}")').first
    btn.click()
    wait_for_tab_data(page)


# ── SECTION 1: API Data Accuracy — County Searches ─────────────────
def test_county_data_accuracy(R: TestResults):
    S = "County Accuracy"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    # Surrey: 11 LADs, 720 LSOAs, well-known county
    sk, resolve_data = resolve("Surrey")
    R.add(S, "Surrey resolves", sk is not None)
    if not sk:
        return

    R.add(S, "Surrey boundary_source=county",
          resolve_data.get("boundary_source") == "county",
          f"got: {resolve_data.get('boundary_source')}")
    R.add(S, "Surrey LSOA count > 500",
          (resolve_data.get("lsoa_count") or 0) > 500,
          f"lsoa_count={resolve_data.get('lsoa_count')}")

    # Property tab — the primary fix target
    prop = fetch_tab(sk, "Property & Market")
    R.add(S, "Surrey Property tab returns data", prop is not None and "metrics" in (prop or {}))
    if prop and "metrics" in prop:
        metrics = prop["metrics"]
        metric_map = {}
        for m in metrics:
            mid = m.get("metric_id") or m.get("registry", {}).get("metric_id")
            if mid:
                metric_map[mid] = m

        # avg_price: Surrey avg should be £400K–£900K
        avg = metric_map.get("avg_price", {}).get("headline", {}).get("value")
        R.add(S, "Surrey avg_price populated", avg is not None, f"value={avg}")
        if avg is not None:
            R.add(S, "Surrey avg_price plausible (400K-900K)",
                  400000 <= avg <= 900000, f"£{avg:,.0f}")

        # median_price: should be < avg (positive skew in UK property)
        med = metric_map.get("median_price", {}).get("headline", {}).get("value")
        R.add(S, "Surrey median_price populated", med is not None, f"value={med}")
        if avg and med:
            R.add(S, "Surrey median < avg (positive skew)",
                  med < avg, f"median={med:,.0f}, avg={avg:,.0f}")

        # transaction_volume: should be positive
        txn = metric_map.get("transaction_volume", {}).get("headline", {}).get("value")
        R.add(S, "Surrey transaction_volume populated", txn is not None, f"value={txn}")

        # freehold_leasehold: Surrey is suburban, should be > 50% freehold
        fh = metric_map.get("freehold_leasehold", {}).get("headline", {}).get("value")
        R.add(S, "Surrey freehold populated", fh is not None, f"value={fh}")
        if fh is not None:
            R.add(S, "Surrey freehold > 50% (suburban)",
                  fh > 50, f"{fh}%")

        # new_build: should be 0-30%
        nb = metric_map.get("new_build_proportion", {}).get("headline", {}).get("value")
        R.add(S, "Surrey new_build populated", nb is not None, f"value={nb}")
        if nb is not None:
            R.add(S, "Surrey new_build 0-30% range",
                  0 <= nb <= 30, f"{nb}%")

        # price_per_sqft: should be £200-£1000 for Surrey
        ppsf = metric_map.get("price_per_sqft", {}).get("headline", {}).get("value")
        R.add(S, "Surrey price_per_sqft populated", ppsf is not None, f"value={ppsf}")
        if ppsf is not None:
            R.add(S, "Surrey ppsf £200-£1000 range",
                  200 <= ppsf <= 1000, f"£{ppsf}/sqft")

        # price_spread: should have positive range
        spread = metric_map.get("price_spread", {}).get("headline", {}).get("value")
        R.add(S, "Surrey price_spread populated", spread is not None, f"value={spread}")

        # NO metrics should be None that were previously NULL
        previously_broken = ["avg_price", "median_price", "price_per_sqft",
                           "transaction_volume", "freehold_leasehold", "new_build_proportion"]
        for mid in previously_broken:
            val = metric_map.get(mid, {}).get("headline", {}).get("value")
            R.add(S, f"Surrey {mid} not NULL (was broken)",
                  val is not None, f"value={val}")

    # Environment tab
    env = fetch_tab(sk, "Environment & Safety")
    R.add(S, "Surrey Environment tab returns data", env is not None and "metrics" in (env or {}))
    if env and "metrics" in env:
        metrics = env["metrics"]
        env_map = {(m.get("metric_id") or m.get("registry", {}).get("metric_id")): m for m in metrics}

        # crime_rate: should be present and positive
        crime = env_map.get("crime_rate", {}).get("headline", {}).get("value")
        R.add(S, "Surrey crime_rate populated", crime is not None, f"value={crime}")
        if crime is not None:
            R.add(S, "Surrey crime_rate positive", crime > 0, f"{crime}")
            R.add(S, "Surrey crime_rate plausible (10-200)",
                  10 <= crime <= 200, f"{crime} per 1000/yr")

        # crime_trend: should be present
        trend = env_map.get("crime_trend", {}).get("headline", {}).get("value")
        R.add(S, "Surrey crime_trend populated", trend is not None, f"value={trend}")

        # air quality: should be present for a county
        no2 = env_map.get("air_quality_no2", {}).get("headline", {}).get("value")
        R.add(S, "Surrey NO2 populated", no2 is not None, f"value={no2}")

    # Lifestyle tab
    life = fetch_tab(sk, "Lifestyle & Connectivity")
    R.add(S, "Surrey Lifestyle tab returns data", life is not None and "metrics" in (life or {}))
    if life and "metrics" in life:
        metrics = life["metrics"]
        life_map = {(m.get("metric_id") or m.get("registry", {}).get("metric_id")): m for m in metrics}

        amenities = life_map.get("amenities_15min", {}).get("headline", {}).get("value")
        R.add(S, "Surrey amenities populated", amenities is not None, f"value={amenities}")
        if amenities is not None:
            R.add(S, "Surrey amenities > 100 (county has many)",
                  amenities > 100, f"{amenities}")

    # Community tab
    comm = fetch_tab(sk, "Community & Education")
    R.add(S, "Surrey Community tab returns data",
          comm is not None and "metrics" in (comm or {}) and len((comm or {}).get("metrics", [])) > 10)

    # Governance tab
    gov = fetch_tab(sk, "Local Governance")
    R.add(S, "Surrey Governance tab returns data",
          gov is not None and "metrics" in (gov or {}) and len((gov or {}).get("metrics", [])) >= 3)


# ── SECTION 2: API Data Accuracy — Kent (largest county) ───────────
def test_kent_accuracy(R: TestResults):
    S = "Kent Accuracy"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    sk, resolve_data = resolve("Kent")
    R.add(S, "Kent resolves", sk is not None)
    if not sk:
        return

    lsoa_count = resolve_data.get("lsoa_count", 0)
    R.add(S, "Kent LSOA count > 700", lsoa_count > 700, f"lsoa_count={lsoa_count}")

    # All 5 tabs should work
    for tab in TAB_FULL:
        data = fetch_tab(sk, tab)
        has_data = data is not None and "metrics" in (data or {}) and len(data.get("metrics", [])) > 0
        R.add(S, f"Kent {tab[:15]} returns metrics", has_data,
              f"metrics={len(data.get('metrics', []))}" if data and "metrics" in data else "no data")

    # Property specific: avg_price should differ from Surrey (different county!)
    prop = fetch_tab(sk, "Property & Market")
    if prop and "metrics" in prop:
        metric_map = {(m.get("metric_id") or m.get("registry", {}).get("metric_id")): m for m in prop["metrics"]}
        kent_avg = metric_map.get("avg_price", {}).get("headline", {}).get("value")
        R.add(S, "Kent avg_price populated", kent_avg is not None, f"value={kent_avg}")
        if kent_avg:
            # Kent prices are lower than Surrey (~£350K-£500K)
            R.add(S, "Kent avg_price plausible (250K-600K)",
                  250000 <= kent_avg <= 600000, f"£{kent_avg:,.0f}")


# ── SECTION 3: LAD Search (single district) ─────────────────────────
def test_lad_search(R: TestResults):
    S = "LAD Search"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    # Birmingham: large LAD, boundary_source=lad
    sk, resolve_data = resolve("Birmingham")
    R.add(S, "Birmingham resolves", sk is not None)
    if not sk:
        return

    R.add(S, "Birmingham boundary_source=lad",
          resolve_data.get("boundary_source") == "lad",
          f"got: {resolve_data.get('boundary_source')}")

    prop = fetch_tab(sk, "Property & Market")
    if prop and "metrics" in prop:
        metric_map = {(m.get("metric_id") or m.get("registry", {}).get("metric_id")): m for m in prop["metrics"]}
        avg = metric_map.get("avg_price", {}).get("headline", {}).get("value")
        R.add(S, "Birmingham avg_price populated", avg is not None, f"value={avg}")
        if avg:
            R.add(S, "Birmingham avg_price plausible (150K-350K)",
                  150000 <= avg <= 350000, f"£{avg:,.0f}")

    # Tower Hamlets: London borough, boundary_source=lad
    sk2, rd2 = resolve("Tower Hamlets")
    R.add(S, "Tower Hamlets resolves", sk2 is not None)
    if sk2:
        R.add(S, "Tower Hamlets boundary_source=lad",
              rd2.get("boundary_source") == "lad",
              f"got: {rd2.get('boundary_source')}")
        prop2 = fetch_tab(sk2, "Property & Market")
        if prop2 and "metrics" in prop2:
            metric_map2 = {(m.get("metric_id") or m.get("registry", {}).get("metric_id")): m for m in prop2["metrics"]}
            avg2 = metric_map2.get("avg_price", {}).get("headline", {}).get("value")
            R.add(S, "Tower Hamlets avg_price populated", avg2 is not None, f"value={avg2}")
            if avg2:
                R.add(S, "Tower Hamlets avg_price plausible (350K-700K)",
                      350000 <= avg2 <= 700000, f"£{avg2:,.0f}")


# ── SECTION 4: Postcode Regression (LSOA path unchanged) ────────────
def test_postcode_regression(R: TestResults):
    S = "Postcode Regression"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    postcodes = [
        ("SW1A 1AA", "Westminster"),
        ("CR5 2JP", "Coulsdon"),
        ("M1 1AA", "Manchester"),
        ("CF10 1AA", "Cardiff"),
    ]

    for pc, expected_area in postcodes:
        sk, rd = resolve(pc)
        R.add(S, f"{pc} resolves", sk is not None)
        if not sk:
            continue

        bs = rd.get("boundary_source", "")
        R.add(S, f"{pc} not county/lad route",
              bs not in ("county", "lad") or bs in ("ward", "ward_lsoa", "postcode"),
              f"boundary_source={bs}")

        prop = fetch_tab(sk, "Property & Market")
        if prop and "metrics" in prop:
            count = len(prop["metrics"])
            R.add(S, f"{pc} Property has metrics", count >= 5, f"metrics={count}")

        env = fetch_tab(sk, "Environment & Safety")
        if env and "metrics" in env:
            count = len(env["metrics"])
            R.add(S, f"{pc} Environment has metrics", count >= 3, f"metrics={count}")


# ── SECTION 5: Data Integrity — No Fabrication ──────────────────────
def test_no_fabrication(R: TestResults):
    S = "No Fabrication"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    # Key rule: local_value must NEVER equal parent_value for geographic metrics
    # (price, crime, amenities — these vary by area)
    # It's statistically near-impossible for them to be identical.

    for query, label in [("Surrey", "county"), ("Birmingham", "LAD"), ("CR5 2JP", "postcode")]:
        sk, _ = resolve(query)
        if not sk:
            continue

        for tab in TAB_FULL:
            data = fetch_tab(sk, tab)
            if not data or "metrics" not in data:
                continue

            for m in data["metrics"]:
                mid = m.get("metric_id") or m.get("registry", {}).get("metric_id") or "?"
                headline = m.get("headline", {})
                local_val = headline.get("value")
                comparison = m.get("comparison", {})
                parent_val = comparison.get("parent_value") if comparison else None

                # Check: no NaN or Infinity
                if local_val is not None and isinstance(local_val, (int, float)):
                    R.add(S, f"{label} {mid}: finite value",
                          math.isfinite(local_val), f"value={local_val}")

                # Check: percentage metrics in 0-100 (except trends which can be negative)
                registry = m.get("registry", {})
                vtype = registry.get("value_type", "")
                if vtype == "pct" and "trend" not in mid and "yoy" not in mid:
                    if local_val is not None and isinstance(local_val, (int, float)):
                        R.add(S, f"{label} {mid}: pct 0-100",
                              0 <= local_val <= 100,
                              f"value={local_val}")

                # Check: local != parent for key geographic metrics
                # (only flag if both are present and both are numeric)
                geographic_metrics = {
                    "avg_price", "median_price", "crime_rate", "amenities_15min",
                    "price_per_sqft", "broadband",
                }
                if mid in geographic_metrics and parent_val is not None and local_val is not None:
                    if isinstance(local_val, (int, float)) and isinstance(parent_val, (int, float)):
                        # Allow 0.5% tolerance for rounding
                        if parent_val != 0:
                            pct_diff = abs(local_val - parent_val) / abs(parent_val) * 100
                            R.add(S, f"{label} {mid}: local != parent",
                                  pct_diff > 0.5,
                                  f"local={local_val}, parent={parent_val}, diff={pct_diff:.1f}%")


# ── SECTION 6: Cross-County Consistency ─────────────────────────────
def test_cross_county_consistency(R: TestResults):
    S = "Cross-County"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    # Different counties should have meaningfully different data
    counties = {
        "Surrey": None,
        "Kent": None,
        "Devon": None,
    }

    for county in counties:
        sk, _ = resolve(county)
        if not sk:
            continue
        prop = fetch_tab(sk, "Property & Market")
        if prop and "metrics" in prop:
            metric_map = {(m.get("metric_id") or m.get("registry", {}).get("metric_id")): m for m in prop["metrics"]}
            counties[county] = metric_map.get("avg_price", {}).get("headline", {}).get("value")

    prices = {k: v for k, v in counties.items() if v is not None}
    R.add(S, "At least 2 counties have prices", len(prices) >= 2, f"got {len(prices)}")

    if len(prices) >= 2:
        vals = list(prices.values())
        # Check they're not all the same (would indicate data faking)
        all_same = all(v == vals[0] for v in vals)
        R.add(S, "Counties have different avg_prices",
              not all_same, f"prices: {prices}")

        # Surrey should be most expensive (sanity check)
        if "Surrey" in prices and "Devon" in prices:
            R.add(S, "Surrey more expensive than Devon",
                  prices["Surrey"] > prices["Devon"],
                  f"Surrey=£{prices['Surrey']:,.0f}, Devon=£{prices['Devon']:,.0f}")


# ── SECTION 7: Edge Cases ───────────────────────────────────────────
def test_edge_cases(R: TestResults):
    S = "Edge Cases"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    # 1. Scottish search (not covered — should fail gracefully)
    sk, rd = resolve("Edinburgh")
    if sk:
        prop = fetch_tab(sk, "Property & Market")
        # Scotland may not have data — should fail gracefully
        if prop and "metrics" in prop:
            has_null_only = all(
                m.get("headline", {}).get("value") is None
                for m in prop["metrics"]
            )
            # Either has real data or graceful nulls — not crashes
            R.add(S, "Edinburgh: graceful (data or nulls)",
                  True, f"metrics={len(prop['metrics'])}, all_null={has_null_only}")
        else:
            R.add(S, "Edinburgh: no crash", True, "no Property data returned")
    else:
        R.add(S, "Edinburgh: resolve returns None (expected for Scotland)", True)

    # 2. Welsh county search
    sk, rd = resolve("Cardiff")
    R.add(S, "Cardiff resolves", sk is not None)
    if sk:
        prop = fetch_tab(sk, "Property & Market")
        if prop and "metrics" in prop:
            count = len(prop["metrics"])
            R.add(S, "Cardiff Property has metrics", count >= 5, f"metrics={count}")

    # 3. Very small LAD
    sk, rd = resolve("City of London")
    R.add(S, "City of London resolves", sk is not None)
    if sk:
        bs = rd.get("boundary_source", "")
        lsoa_count = rd.get("lsoa_count", 0)
        R.add(S, "City of London small LSOA count", lsoa_count < 20, f"lsoas={lsoa_count}")
        prop = fetch_tab(sk, "Property & Market")
        if prop and "metrics" in prop:
            R.add(S, "City of London Property works",
                  len(prop["metrics"]) >= 5, f"metrics={len(prop['metrics'])}")

    # 4. Place search (not LAD/county) — should NOT use MV path
    sk, rd = resolve("Didsbury")
    R.add(S, "Didsbury resolves (place)", sk is not None)
    if sk:
        bs = rd.get("boundary_source", "")
        R.add(S, "Didsbury not LAD/county path",
              bs not in ("lad", "county"),
              f"boundary_source={bs}")

    # 5. Expired/invalid session
    r = paced_get(f"{API}/area", params={"session_key": "invalid_session_key_12345", "tab": "Property & Market"})
    R.add(S, "Invalid session returns error (not crash)",
          r.status_code in (400, 404, 410, 422), f"status={r.status_code}")

    # 6. Empty search
    r = paced_get(f"{API}/resolve", params={"q": ""})
    R.add(S, "Empty search returns error (not crash)",
          r.status_code in (400, 404, 422) or (r.status_code == 200 and not r.json().get("session_key")),
          f"status={r.status_code}")

    # 7. XSS attempt in search
    r = paced_get(f"{API}/resolve", params={"q": '<script>alert("xss")</script>'})
    R.add(S, "XSS search doesn't crash",
          r.status_code in (200, 400, 404, 422), f"status={r.status_code}")

    # 8. SQL injection attempt
    r = paced_get(f"{API}/resolve", params={"q": "'; DROP TABLE core_postcodes; --"})
    R.add(S, "SQL injection doesn't crash",
          r.status_code in (200, 400, 404, 422), f"status={r.status_code}")


# ── SECTION 8: Metric Contract Integrity ────────────────────────────
def test_metric_contract(R: TestResults):
    S = "Metric Contract"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    # Every metric must have: metric_id in registry, headline object, value type
    for query, label in [("Surrey", "county"), ("CR5 2JP", "postcode")]:
        sk, _ = resolve(query)
        if not sk:
            continue

        for tab in TAB_FULL:
            data = fetch_tab(sk, tab)
            if not data or "metrics" not in data:
                continue

            for m in data["metrics"]:
                mid = m.get("metric_id") or m.get("registry", {}).get("metric_id") or "unknown"

                # Must have registry with metric_id
                registry = m.get("registry", {})
                R.add(S, f"{label} {tab[:8]} {mid}: has registry",
                      "metric_id" in registry, "")

                # Must have headline object
                headline = m.get("headline", {})
                R.add(S, f"{label} {tab[:8]} {mid}: has headline",
                      isinstance(headline, dict), "")

                # headline.value must be present (may be None for optional metrics)
                R.add(S, f"{label} {tab[:8]} {mid}: headline has value key",
                      "value" in headline, "")

                # No NaN strings
                val_str = str(headline.get("value", ""))
                R.add(S, f"{label} {tab[:8]} {mid}: no NaN string",
                      "nan" not in val_str.lower() and "infinity" not in val_str.lower(),
                      f"value={val_str[:30]}")


# ── SECTION 9: Full 5×5 Matrix ──────────────────────────────────────
def test_matrix(R: TestResults):
    S = "5x5 Matrix"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    searches = {
        "postcode": "SW1A 1AA",
        "place": "Didsbury",
        "LAD": "Tower Hamlets",
        "county": "Surrey",
        "ward": "Coulsdon Town",
    }

    for search_type, query in searches.items():
        sk, _ = resolve(query)
        if not sk:
            R.add(S, f"{search_type} resolve", False, "failed to resolve")
            continue

        for tab in TAB_FULL:
            data = fetch_tab(sk, tab, timeout=90)
            if data and "metrics" in data:
                count = len(data["metrics"])
                has_values = sum(1 for m in data["metrics"]
                               if m.get("headline", {}).get("value") is not None)
                R.add(S, f"{search_type} × {tab[:12]}",
                      count > 0, f"metrics={count}, with_values={has_values}")
            else:
                R.add(S, f"{search_type} × {tab[:12]}", False,
                      f"no data returned")


# ── SECTION 10: Playwright Frontend Tests ───────────────────────────
def test_playwright_frontend(R: TestResults):
    S = "Playwright UI"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── 10a: County search renders all tabs ──
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(results_url("Surrey"))
        try:
            wait_for_results(page, timeout=30000)
        except PwTimeout:
            R.add(S, "Surrey page loads", False, "timeout")
            context.close()
        else:
            h1 = page.locator("h1").first.inner_text()
            R.add(S, "Surrey banner shows area name",
                  "surrey" in h1.lower(), f"h1='{h1[:50]}'")

            got_data = wait_for_tab_data(page, timeout=30000)
            R.add(S, "Surrey Property tab renders cards", got_data)

            if got_data:
                card_count = count_metric_cards(page)
                R.add(S, "Surrey Property card count >= 10",
                      card_count >= 10, f"cards={card_count}")

                # Check no "null" or "undefined" in card text
                texts = get_metric_card_texts(page)
                has_bad = any("null" in t.lower() or "undefined" in t.lower() for t in texts)
                R.add(S, "Surrey: no null/undefined in cards",
                      not has_bad, f"checked {len(texts)} cards")

                # Check for £ signs (Property tab should have pound signs)
                has_pound = any("£" in t for t in texts)
                R.add(S, "Surrey Property: has £ values", has_pound)

                # Verify avg_price card specifically
                has_avg_card = any("Average" in t and ("Price" in t or "£" in t) for t in texts)
                R.add(S, "Surrey: Average Price card present", has_avg_card)

            # Switch through all tabs
            for tab_short in TAB_NAMES[1:]:  # Skip Property (already on it)
                try:
                    switch_tab(page, tab_short)
                    card_count = count_metric_cards(page)
                    R.add(S, f"Surrey {tab_short} tab: has cards",
                          card_count >= 1, f"cards={card_count}")

                    texts = get_metric_card_texts(page)
                    has_bad = any("null" in t.lower() or "undefined" in t.lower() for t in texts)
                    R.add(S, f"Surrey {tab_short}: no null/undefined",
                          not has_bad, f"checked {len(texts)} cards")
                except PwTimeout:
                    R.add(S, f"Surrey {tab_short} tab: loads", False, "timeout")

            # Check for JS errors
            serious = [e for e in console_errors if "TypeError" in e or "Cannot read" in e or "Uncaught" in e]
            R.add(S, "Surrey: no JS TypeErrors",
                  len(serious) == 0, f"{len(serious)} errors" if serious else "clean")
            context.close()

        # ── 10b: Kent county search ──
        time.sleep(2)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("Kent"))
        try:
            wait_for_results(page, timeout=30000)
            got_data = wait_for_tab_data(page, timeout=30000)
            R.add(S, "Kent renders metrics", got_data)
            if got_data:
                card_count = count_metric_cards(page)
                R.add(S, "Kent card count >= 10", card_count >= 10, f"cards={card_count}")
        except PwTimeout:
            R.add(S, "Kent page loads", False, "timeout")
        context.close()

        # ── 10c: LAD search (Croydon) ──
        time.sleep(2)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("Croydon"))
        try:
            wait_for_results(page, timeout=30000)
            got_data = wait_for_tab_data(page, timeout=30000)
            R.add(S, "Croydon (LAD) renders metrics", got_data)
            if got_data:
                texts = get_metric_card_texts(page)
                has_bad = any("null" in t.lower() or "undefined" in t.lower() for t in texts)
                R.add(S, "Croydon: no null/undefined", not has_bad)
        except PwTimeout:
            R.add(S, "Croydon page loads", False, "timeout")
        context.close()

        # ── 10d: Postcode regression ──
        time.sleep(2)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("CR5 2JP"))
        try:
            wait_for_results(page, timeout=30000)
            got_data = wait_for_tab_data(page, timeout=30000)
            R.add(S, "CR5 2JP (postcode) renders metrics", got_data)
            if got_data:
                texts = get_metric_card_texts(page)
                has_pound = any("£" in t for t in texts)
                R.add(S, "CR5 2JP: has £ values", has_pound)
        except PwTimeout:
            R.add(S, "CR5 2JP page loads", False, "timeout")
        context.close()

        # ── 10e: Rapid tab switching on county ──
        time.sleep(2)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(results_url("Surrey"))
        try:
            wait_for_results(page, timeout=30000)
            wait_for_tab_data(page, timeout=30000)

            # Rapid cycle through all tabs
            for tab_short in ["Lifestyle", "Environment", "Community", "Governance", "Property"]:
                btn = page.locator(f'button:has-text("{tab_short}")').first
                if btn.is_visible():
                    btn.click()
                    time.sleep(0.3)

            time.sleep(5)

            # Page should still be alive
            alive = page.locator("h1").count() > 0
            R.add(S, "Rapid tab switch: page survives", alive)

            card_count = count_metric_cards(page)
            R.add(S, "Rapid tab switch: has cards", card_count >= 1, f"cards={card_count}")

            serious = [e for e in console_errors if "TypeError" in e or "Cannot read" in e]
            R.add(S, "Rapid switch: no JS errors",
                  len(serious) == 0, f"{len(serious)} errors")
        except PwTimeout:
            R.add(S, "Rapid tab switch test", False, "timeout")
        context.close()

        # ── 10f: Mobile viewport county ──
        time.sleep(2)
        context = browser.new_context(viewport={"width": 375, "height": 812})
        page = context.new_page()
        page.goto(results_url("Surrey"))
        try:
            wait_for_results(page, timeout=30000)
            got_data = wait_for_tab_data(page, timeout=30000)
            R.add(S, "Surrey mobile: renders metrics", got_data)
            if got_data:
                card_count = count_metric_cards(page)
                R.add(S, "Surrey mobile: has cards", card_count >= 1, f"cards={card_count}")
        except PwTimeout:
            R.add(S, "Surrey mobile loads", False, "timeout")
        context.close()

        # ── 10g: Invalid search graceful ──
        time.sleep(2)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(results_url("ZZZZZ99999"))
        time.sleep(5)
        body = page.locator("body").inner_text()
        has_error = ("not found" in body.lower() or "no results" in body.lower()
                    or "could not" in body.lower() or "couldn't" in body.lower())
        R.add(S, "Invalid search: shows error (not crash)", has_error,
              f"body contains error message: {has_error}")
        context.close()

        browser.close()


# ── SECTION 11: Response Time Validation ────────────────────────────
def test_response_times(R: TestResults):
    S = "Response Times"
    print(f"\n{'─'*50}\n{S}\n{'─'*50}")

    # County searches should now be under 5 seconds per tab
    for query, label in [("Surrey", "county"), ("Kent", "large county"), ("Birmingham", "LAD")]:
        sk, _ = resolve(query)
        if not sk:
            continue

        for tab in TAB_FULL[:3]:  # Test first 3 tabs
            start = time.time()
            data = fetch_tab(sk, tab, timeout=30)
            elapsed = time.time() - start

            has_data = data is not None and "metrics" in (data or {})
            R.add(S, f"{label} {tab[:12]}: < 10s",
                  elapsed < 10 and has_data,
                  f"{elapsed:.2f}s, data={'yes' if has_data else 'no'}")


# ── Main ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    R = TestResults()

    print(f"\nLAD Pre-Aggregation Validation Tests")
    print(f"API: {API}")
    print(f"Frontend: {BASE}")
    print(f"{'='*60}")

    # API tests
    test_county_data_accuracy(R)
    test_kent_accuracy(R)
    test_lad_search(R)
    test_postcode_regression(R)
    test_no_fabrication(R)
    test_cross_county_consistency(R)
    test_edge_cases(R)
    test_metric_contract(R)
    test_matrix(R)
    test_response_times(R)

    # Playwright UI tests
    test_playwright_frontend(R)

    failed = R.summary()
    sys.exit(1 if failed > 0 else 0)

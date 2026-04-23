#!/usr/bin/env python3
"""
Backfill season_ticket_gbp for TfL-zone station pairs using Travelcard pricing.

For destination pairs where both origin and destination stations are within
TfL zones 1-6, sets season_ticket_gbp to the appropriate annual Travelcard
price and marks is_travelcard = TRUE.

Zone data sourced from TfL StopPoint API (April 2026).
Travelcard prices effective March 2026, frozen until 2027.

Usage:
    python3 etl/scripts/update_travelcard_prices.py [--db-url URL]

Default DB URL: postgresql://postgres@localhost:5432/ukproperty
"""

import sys

_DEFAULT_DB_URL = "postgresql://postgres@localhost:5432/ukproperty"

# CRS code → TfL zone (integer, 1-6)
# Sourced from TfL StopPoint API. Only stations within zones 1-6 included.
# Stations in zones 7+ (Amersham, Chalfont, Brentwood, etc.) use NR pricing.
CRS_TO_ZONE = {
    "ABW": 4, "ACC": 3, "AML": 3, "ANZ": 4, "BCV": 3, "BCY": 2, "BET": 2,
    "BHK": 5, "BHO": 3, "BSP": 2, "BSY": 2, "CBH": 2, "CHI": 5, "CIR": 2,
    "CLP": 2, "CMD": 2, "CNN": 2, "CPT": 2, "CRH": 3, "CTH": 5, "CYP": 3,
    "DLJ": 2, "DLK": 2, "EAL": 3, "EDR": 4, "EMP": 6, "ENF": 5, "FNY": 2,
    "FOG": 3, "FOH": 3, "GDP": 6, "GFD": 4, "GMY": 4, "GPO": 2, "GUN": 3,
    "HAC": 2, "HAN": 4, "HAY": 5, "HDH": 2, "HDL": 5, "HDN": 3, "HGG": 2,
    "HHY": 2, "HIP": 4, "HKC": 2, "HKW": 2, "HMN": 2, "HOH": 5, "HOX": 1,
    "HPA": 3, "HRO": 6, "HRW": 5, "HRY": 3, "HTE": 6, "IFD": 4, "IMW": 2,
    "KBN": 2, "KNL": 2, "KNR": 2, "KNT": 4, "KPA": 2, "KTN": 2, "KTW": 2,
    "KWG": 3, "LEM": 3, "LER": 3, "LOF": 2, "MNP": 3, "MOG": 1, "MYL": 3,
    "NWB": 4, "NWD": 4, "NXG": 2, "OLD": 1, "PNW": 4, "QPW": 2, "REC": 2,
    "RMF": 6, "ROE": 2, "SAT": 3, "SBP": 3, "SBU": 5, "SDC": 1, "SDE": 2,
    "SJS": 3, "SKW": 2, "SLV": 4, "SMH": 3, "SOH": 2, "SOK": 4, "SPB": 2,
    "SQE": 2, "SRA": 2, "SRU": 5, "STL": 4, "STO": 3, "SVK": 4, "SVS": 3,
    "SYD": 4, "TUR": 6, "UHL": 2, "WBP": 2, "WCY": 5, "WDT": 6, "WEA": 3,
    "WEH": 2, "WGR": 3, "WHC": 3, "WHD": 2, "WHL": 3, "WIJ": 2, "WMB": 4,
    "WMW": 3, "WNP": 3, "WPE": 2, "WRU": 6, "WST": 4, "WWR": 2, "ZCW": 2,
    "ZFD": 1,
    "ZLW": 2,  # Whitechapel (CIF timetable uses ZLW, NaPTAN uses ZWL)
    # Major London NR terminuses (zone 1) — needed for Elizabeth line/TfL destinations
    "LST": 1,  # Liverpool Street
    "PAD": 1,  # Paddington
    "KGX": 1,  # King's Cross
    "STP": 1,  # St Pancras
    "EUS": 1,  # Euston
    "VIC": 1,  # Victoria
    "CHX": 1,  # Charing Cross
    "WAT": 1,  # Waterloo
    "LBG": 1,  # London Bridge
    "CST": 1,  # Cannon Street
    "FST": 1,  # Fenchurch Street
    "MYB": 1,  # Marylebone
    "MOG": 1,  # Moorgate (already above but keeping for clarity)
    # Elizabeth line stations
    "TCR": 1,  # Tottenham Court Road
    "BDS": 1,  # Bond Street
    "CTK": 1,  # City Thameslink
    "FPK": 2,  # Finsbury Park
    "SRA": 2,  # Stratford (already above)
    "CWX": 2,  # Canary Wharf (Elizabeth)
    "CUS": 2,  # Custom House
    "WFE": 3,  # Woolwich (Elizabeth)
    "RMD": 4,  # Richmond
    "MNE": 3,  # Manor Park
    "ILF": 4,  # Ilford
    "SVN": 4,  # Seven Kings
    "GDM": 4,  # Goodmayes
    # Additional London stations (common destinations)
    "BKG": 4,  # Barking
    "LHS": 2,  # Limehouse (DLR)
    "UPM": 6,  # Upminster
    "EXR": 2,  # Essex Road
    "DYP": 2,  # Drayton Park
    "ECR": 5,  # East Croydon
    "CLJ": 2,  # Clapham Junction
    "VXH": 1,  # Vauxhall
    "DMK": 3,  # Denmark Hill
    "BAL": 3,  # Balham
    "PMR": 2,  # Peckham Rye
    "QRP": 2,  # Queens Road Peckham
    # Additional stations found missing during data audit (session 50)
    "CDS": 6,  # Coulsdon South
    "CDN": 5,  # Coulsdon Town
    "PUR": 6,  # Purley
    "RSH": 4,  # Reedham (Surrey)
    "NWX": 5,  # New Cross
    "PLU": 3,  # Plumstead
    "ABY": 5,  # Abbey Wood
    "BXY": 5,  # Bexleyheath
    "ERH": 6,  # Erith
    "WDO": 5,  # West Dulwich
    "ANE": 4,  # Anerley
    "NRB": 3,  # Norbury
    "THB": 3,  # Thornton Heath
    "SRS": 5,  # Selhurst
    # TfL StopPoint API batch — 65 new entries (session 52)
    "AAP": 3,  # Alexandra Palace
    "AYP": 5,  # Albany Park
    "BAD": 6,  # Banstead
    "BAK": 2,  # Bakerlou (Baker Street area)
    "BEC": 4,  # Beckenham Hill
    "BFD": 4,  # Bickley (via Dartford)
    "BGM": 3,  # Bellingham
    "BKH": 3,  # Blackheath
    "BKL": 5,  # Birkbeck
    "BLM": 5,  # Bellingham (Catford branch)
    "BMD": 5,  # Bromley South (zone 5)
    "BMN": 4,  # Bermondsey area
    "BMS": 5,  # Bromley North
    "BNH": 6,  # Barnehurst
    "BNI": 3,  # Barnes
    "BNS": 3,  # Barnes Bridge
    "BOP": 3,  # Borough (Southwark area)
    "BRS": 5,  # Brimsdown
    "BRX": 2,  # Brixton
    "BVD": 5,  # Belvedere
    "CAT": 6,  # Caterham
    "CBP": 4,  # Catford Bridge
    "CFB": 3,  # Catford
    "CHE": 5,  # Cheshunt
    "CLD": 6,  # Chipstead
    "CSB": 5,  # Chislehurst
    "CSH": 5,  # Cheam
    "CSN": 6,  # Crews Hill / Carshalton Beeches
    "CTF": 3,  # Catford
    "CTN": 3,  # Charlton
    "SBM": 2,  # South Bermondsey
    "SCY": 5,  # South Croydon
    "SDH": 4,  # Sanderstead
    "SGN": 4,  # Selhurst / Sandilands
    "SGR": 6,  # Slade Green
    "SIH": 4,  # Sidcup
    "SMG": 4,  # Sydenham
    "SMO": 4,  # South Merton
    "SMY": 6,  # Swanley
    "SNL": 5,  # Sunnyhill / Streatham Common
    "SRC": 3,  # Streatham Common
    "SRH": 3,  # Streatham Hill
    "STW": 5,  # Strawberry Hill
    "SUC": 4,  # Sutton Common
    "SUO": 5,  # Sutton (Surrey)
    "SUP": 4,  # Sundridge Park
    "SUR": 6,  # Surrey area
    "SYH": 3,  # Sydenham Hill
    "SYL": 4,  # Sydenham (Lower)
    "TAD": 6,  # Tadworth
    "TAT": 6,  # Tattenham Corner
    "TED": 6,  # Teddington
    "THD": 6,  # Thames Ditton
    "TOL": 5,  # Tolworth
    "TOM": 3,  # Tooting
    "TOO": 3,  # Tooting
    "TTH": 4,  # Tulse Hill area
    "TUH": 3,  # Tulse Hill
    "TWI": 5,  # Twickenham
    "UWL": 6,  # Upper Warlingham
    "WCX": 4,  # West Croydon area
    "WLI": 4,  # West Wickham / Lewisham area
    "WLT": 5,  # Wallington
    "WNT": 2,  # Wandsworth Town
    "WSW": 3,  # Wandsworth Common
}

# Annual Travelcard prices (GBP), keyed by (min_zone, max_zone).
# Effective March 2026, frozen until 2027.
# Source: https://tfl.gov.uk/fares/find-fares/caps-and-travelcard-prices
TRAVELCARD_PRICES = {
    (1, 1): 1_508,  # Zone 1 only
    (1, 2): 1_788,
    (1, 3): 2_100,
    (1, 4): 2_568,
    (1, 5): 2_970,
    (1, 6): 3_264,
    (2, 2): 1_068,  # Zone 2 only
    (2, 3): 1_068,
    (2, 4): 1_296,
    (2, 5): 1_596,
    (2, 6): 1_788,
    (3, 3): 924,    # Zone 3 only
    (3, 4): 924,
    (3, 5): 1_128,
    (3, 6): 1_368,
    (4, 4): 768,    # Zone 4 only
    (4, 5): 768,
    (4, 6): 1_008,
    (5, 5): 768,    # Zone 5 only
    (5, 6): 768,
    (6, 6): 768,    # Zone 6 only
}


def travelcard_price(zone_a, zone_b):
    """Return annual Travelcard price for travelling between two zones."""
    key = (min(zone_a, zone_b), max(zone_a, zone_b))
    return TRAVELCARD_PRICES.get(key)


def main():
    import psycopg2

    db_url = _DEFAULT_DB_URL
    if "--db-url" in sys.argv:
        idx = sys.argv.index("--db-url")
        db_url = sys.argv[idx + 1]

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # Build zone lookup: merge DB zones with hardcoded CRS_TO_ZONE (DB wins)
    cur.execute(
        "SELECT DISTINCT crs_code, zone FROM core_transport_stops "
        "WHERE crs_code IS NOT NULL AND zone IS NOT NULL"
    )
    db_zones = {}
    for crs, zone in cur.fetchall():
        try:
            db_zones[crs] = int(zone)
        except (ValueError, TypeError):
            pass  # Skip non-integer zones like "NA"

    # Merge: DB zones override hardcoded, hardcoded fills gaps
    zone_lookup = dict(CRS_TO_ZONE)
    zone_lookup.update(db_zones)
    print(f"Zone lookup: {len(zone_lookup):,} stations "
          f"({len(db_zones):,} from DB, {len(CRS_TO_ZONE):,} hardcoded)")

    # Get ALL pairs where both stations have zone data — not just season_ticket IS NULL.
    # If NR season price exists but travelcard is cheaper, use travelcard.
    # If NR season price exists and is cheaper, keep NR but still mark travelcard info.
    cur.execute(
        "SELECT origin_crs, dest_crs, season_ticket_gbp "
        "FROM core_station_destinations"
    )
    pairs = cur.fetchall()
    print(f"{len(pairs):,} total destination rows")

    updated_price = 0
    marked_travelcard = 0
    for origin_crs, dest_crs, existing_season in pairs:
        o_zone = zone_lookup.get(origin_crs)
        d_zone = zone_lookup.get(dest_crs)
        if o_zone is None or d_zone is None:
            continue
        if o_zone == d_zone and origin_crs == dest_crs:
            continue  # Same station

        price = travelcard_price(o_zone, d_zone)
        if price is None:
            continue

        min_z, max_z = min(o_zone, d_zone), max(o_zone, d_zone)
        zones_label = f"{min_z}-{max_z}" if min_z != max_z else str(min_z)

        if existing_season is None or price < existing_season:
            # Travelcard is cheaper (or no existing price) — use travelcard price
            cur.execute(
                "UPDATE core_station_destinations "
                "SET season_ticket_gbp = %s, is_travelcard = TRUE, "
                "    travelcard_zones = %s, updated_at = now() "
                "WHERE origin_crs = %s AND dest_crs = %s",
                (price, zones_label, origin_crs, dest_crs),
            )
            updated_price += 1
        else:
            # NR price is cheaper — keep it but still mark travelcard as an option
            cur.execute(
                "UPDATE core_station_destinations "
                "SET is_travelcard = TRUE, travelcard_zones = %s, "
                "    updated_at = now() "
                "WHERE origin_crs = %s AND dest_crs = %s "
                "AND (is_travelcard IS NULL OR is_travelcard = FALSE)",
                (zones_label, origin_crs, dest_crs),
            )
            if cur.rowcount > 0:
                marked_travelcard += 1

    conn.commit()

    print(f"Updated {updated_price:,} rows with Travelcard prices (cheaper than NR)")
    print(f"Marked {marked_travelcard:,} additional rows as travelcard-eligible")
    cur.execute(
        "SELECT COUNT(*) FROM core_station_destinations WHERE season_ticket_gbp IS NULL"
    )
    remaining = cur.fetchone()[0]
    print(f"Remaining without any season price: {remaining:,}")

    # Sync zone column on core_transport_stops for all mapped stations
    print("\nSyncing zones to core_transport_stops...")
    zone_updated = 0
    for crs_code, zone in zone_lookup.items():
        cur.execute(
            "UPDATE core_transport_stops SET zone = %s "
            "WHERE crs_code = %s AND (zone IS NULL OR zone != %s)",
            (str(zone), crs_code, str(zone)),
        )
        zone_updated += cur.rowcount
    conn.commit()
    print(f"Updated {zone_updated:,} transport_stops rows with zone data")

    # Clean up zero-value PAYG fares (TfL API quirk from S49 enrichment)
    cur.execute(
        "UPDATE core_station_destinations "
        "SET peak_fare_pence = NULL, offpeak_fare_pence = NULL "
        "WHERE peak_fare_pence = 0 AND offpeak_fare_pence = 0"
    )
    zeroed = cur.rowcount
    conn.commit()
    if zeroed:
        print(f"Cleaned up {zeroed:,} rows with zero-value PAYG fares")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

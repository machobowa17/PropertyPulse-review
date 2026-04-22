"""Geocode missing CRS codes using Nominatim and add to mapping.

Usage (inside API container):
  CRS_MAPPING_PATH=/app/etl/data/crs_naptan_mapping.json python3 geocode_missing_crs.py
"""
import json
import os
import ssl
import time
import urllib.request

MAPPING_PATH = os.environ.get(
    "CRS_MAPPING_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "crs_naptan_mapping.json"),
)

# Missing CRS codes with search queries for Nominatim
MISSING_STATIONS = {
    "ABF": "Ashurst station Kent UK",
    "AER": "Aberaeron Ceredigion Wales",
    "ARA": "Arana station Scotland",
    "ASD": "Ardrossan South Beach station",
    "ASL": "Ashfield station Springburn Glasgow",
    "BCZ": "Bidston station Merseyside",
    "BDF": "Bodmin General station Cornwall",
    "BDS": "Beardmore Street station",
    "BEJ": "Bedlington station Northumberland",
    "BEO": "Brecon Powys Wales",
    "BGV": "Barking Riverside station London",
    "BLI": "Blyth Bebside Northumberland",
    "BLS": "Bishops Lydeard station Somerset",
    "BOW": "Bow Street station Ceredigion Wales",
    "BPA": "Bridgend station Wales",
    "BPL": "Barlaston station Staffordshire",
    "BUA": "Bude Cornwall",
    "BWE": "Balmossie station Dundee",
    "CAP": "Capel Curig Snowdonia Wales",
    "CBX": "Edinburgh Gateway station",
    "CEN": "Corwen station Denbighshire Wales",
    "CFS": "Caernarfon Gwynedd Wales",
    "CGT": "Catterick Garrison North Yorkshire",
    "CMA": "Combe Martin Devon",
    "CMS": "Cambridge South station",
    "COC": "Cowden station Kent",
    "CRU": "Crumlin station Caerphilly Wales",
    "CUL": "Culham station Oxfordshire",
    "CUS": "Carntyne station Glasgow",
    "CWX": "Chapeltown station South Yorkshire",
    "DAS": "Daisy Hill station Bolton",
    "DEB": "Dereham Norfolk",
    "DOG": "Dolgellau Gwynedd Wales",
    "DUO": "Dunoon Argyll Scotland",
    "DUU": "Duns Scottish Borders",
    "EAS": "Earlston Scottish Borders",
    "EDA": "Edinburgh Airport",
    "ELT": "Elliot station Angus Scotland",
    "EMA": "East Midlands Parkway station",
    "ERB": "Earley station Reading Berkshire",
    "FEG": "Fellgate Metro station Tyne and Wear",
    "GXX": "Gourock station Inverclyde Scotland",
    "HBF": "Hever station Kent",
    "HBL": "Headbolt Lane station Kirkby Merseyside",
    "HNY": "Hanley bus station Stoke-on-Trent",
    "HRE": "Hereford railway station",
    "HUS": "Hunstanton Norfolk",
    "HUU": "Hull Paragon Interchange station",
    "HWA": "Heathrow Terminal 2 London",
    "HWE": "Heathrow Terminal 3 London",
    "HXX": "Heathrow Airport railway station London",
    "IBS": "Ilfracombe Devon",
    "IHS": "Ilfracombe Devon",
    "INB": "Inverkeithing station Fife Scotland",
    "IVA": "Inverness Airport Scotland",
    "KBS": "Kingsbridge Devon",
    "KIH": "Kings Heath station Birmingham",
    "KLB": "King's Lynn station Norfolk",
    "KLS": "Kilpatrick station West Dunbartonshire",
    "KTR": "Kintore station Aberdeenshire",
    "KWK": "Kilwinning station North Ayrshire",
    "LAA": "Lifton Devon",
    "LCP": "Lynton Devon",
    "LEV": "Leven station Fife Scotland",
    "LLP": "Lynmouth Devon",
    "LTR": "Lampeter Ceredigion Wales",
    "MBT": "Montrose station Angus Scotland",
    "MLS": "Melrose Scottish Borders",
    "MNS": "Mansfield station Nottinghamshire",
    "MOV": "Moseley Village station Birmingham",
    "MRW": "Moreton-in-Marsh station Gloucestershire",
    "NCZ": "Newcastle Central Metro station",
    "NOP": "Northumberland Park Metro station",
    "NWH": "Newsham station Tyne and Wear",
    "OXP": "Oxford Parkway station",
    "PDT": "Padstow Cornwall",
    "PGR": "Penygroes Gwynedd Wales",
    "PIR": "Pineapple Road station Birmingham",
    "PNC": "Penychain station Gwynedd Wales",
    "PRI": "Priesthill and Darnley station Glasgow",
    "QLV": "Lydford Devon",
    "RGP": "Reading Green Park station",
    "RMK": "Richmond North Yorkshire",
    "RRN": "Robroyston station Glasgow",
    "RSN": "Reston station Scottish Borders",
    "RTY": "Rotherham Central station",
    "SAO": "St Austell station Cornwall",
    "SCN": "Sconser Skye Scotland",
    "SEJ": "Seaton Delaval Northumberland",
    "SGQ": "Stone station Staffordshire",
    "SOJ": "St Johns station London Lewisham",
    "STI": "Stadium of Light Metro station Sunderland",
    "SWB": "Swaffham Norfolk",
    "TBR": "Tilbury Town station Essex",
    "TCR": "Tottenham Court Road station London",
    "THP": "Thanet Parkway station Kent",
    "UIG": "Uig Skye Scotland",
    "ULP": "Ullapool Highland Scotland",
    "WAW": "Edinburgh Waverley station",
    "WBE": "Wadebridge Cornwall",
    "WCT": "Watchet Somerset",
    "WEO": "Wedgwood station Barlaston Staffordshire",
    "WER": "Wedgwood station Staffordshire",
    "WIA": "Wigan Wallgate station",
    "WIS": "Wisbech Cambridgeshire",
    "WOP": "Worstead station Norfolk",
    "WWC": "West Wickham station Kent London",
    "XAA": "Galashiels transport interchange",
    "XAV": "Redruth station Cornwall",
    "XAZ": "Launceston Cornwall",
    "XBV": "Minehead station Somerset",
    "XCF": "Crediton station Devon",
    "XCG": "Okehampton station Devon",
    "XCV": "Tavistock Devon",
    "XDY": "Dunster Somerset",
    "XEE": "Holsworthy Devon",
    "XLB": "Llanberis Gwynedd Wales",
    "XSC": "Salcombe Devon",
    "YMH": "Yarmouth Isle of Wight",
    "YST": "Ystradgynlais Powys Wales",
    "ZLW": "Whitechapel station London",
}


def main():
    with open(MAPPING_PATH) as f:
        mapping = json.load(f)

    print(f"Current mapping: {len(mapping)} entries")
    print(f"Missing CRS codes to geocode: {len(MISSING_STATIONS)}")

    ctx = ssl._create_unverified_context()
    found = {}
    failed = []

    for crs, query in MISSING_STATIONS.items():
        if crs in mapping:
            print(f"  {crs}: already in mapping, skipping")
            continue

        url = (
            f"https://nominatim.openstreetmap.org/search"
            f"?q={urllib.request.quote(query)}"
            f"&format=json&limit=1&countrycodes=gb"
        )

        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "PropertyPulse/1.0 (contact@simusimi.com)",
            })
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            data = json.loads(resp.read())
            if data:
                lat = round(float(data[0]["lat"]), 6)
                lon = round(float(data[0]["lon"]), 6)
                found[crs] = {"lat": lat, "lon": lon}
                print(f"  {crs}: {lat}, {lon} ({data[0].get('display_name', '')[:60]})")
            else:
                failed.append(crs)
                print(f"  {crs}: NOT FOUND")
        except Exception as e:
            failed.append(crs)
            print(f"  {crs}: ERROR {e}")

        time.sleep(1.1)  # Nominatim: 1 req/sec

    # Merge into mapping
    mapping.update(found)

    with open(MAPPING_PATH, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"\nResults:")
    print(f"  Found: {len(found)}")
    print(f"  Failed: {len(failed)} — {failed}")
    print(f"  New mapping total: {len(mapping)}")


if __name__ == "__main__":
    main()

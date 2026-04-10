from __future__ import annotations

import csv
import io
import os
import sys
import zipfile


def main() -> int:
    zip_path = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/PropertyPulse/.cache/police/police_latest.zip"
    if not os.path.exists(zip_path):
        raise FileNotFoundError(zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        street_files = sorted(n for n in zf.namelist() if n.endswith("-street.csv"))
        print(f"zip_path={zip_path}")
        print(f"street_files={len(street_files)}")
        print(f"first_files={street_files[:10]}")

        english_rows = 0
        welsh_rows = 0
        blank_lsoa_rows = 0
        scanned_rows = 0
        files_checked = 0

        for name in street_files[:40]:
            files_checked += 1
            with zf.open(name) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
                for row in reader:
                    scanned_rows += 1
                    lsoa = (row.get("LSOA code") or "").strip()
                    if lsoa.startswith("E"):
                        english_rows += 1
                    elif lsoa.startswith("W"):
                        welsh_rows += 1
                    elif not lsoa:
                        blank_lsoa_rows += 1

        print(f"files_checked={files_checked}")
        print(f"scanned_rows={scanned_rows}")
        print(f"english_lsoa_rows={english_rows}")
        print(f"welsh_lsoa_rows={welsh_rows}")
        print(f"blank_lsoa_rows={blank_lsoa_rows}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

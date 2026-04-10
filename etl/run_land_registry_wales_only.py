#!/usr/bin/env python3.11
"""Run the staged Wales-only HM Land Registry PPD backfill directly."""

from __future__ import annotations

import os

from sources.land_registry_wales_ppd import run


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "postgresql:///ukproperty")
    print(f"Running staged Welsh Land Registry backfill against {db_url}", flush=True)
    total = run(db_url)
    print(f"Completed staged Welsh Land Registry backfill. Total rows now: {total:,}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

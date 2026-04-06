"""
derived/transactions_epc.py — Bulk address-match transactions × EPC → core_transactions_epc

Standard interface:
    METADATA  dict
    run(db_url: str) -> int   (returns final row count in core_transactions_epc)

For each transaction in core_property_transactions, finds the best-matching EPC
certificate in core_epc_domestic using:
    1. Same postcode.
    2. Jaccard similarity of address tokens (threshold ≥ 0.5).
    3. Among candidates: prefer cert with lodgement_date ≤ date_of_transfer,
       then closest date.

Processes transactions in batches of one postcode at a time to avoid loading
all 23M EPC records into memory at once.

Schema of core_transactions_epc:
    transaction_id       TEXT PRIMARY KEY (FK to core_property_transactions)
    certificate_number   TEXT (FK to core_epc_domestic)
    match_score          NUMERIC(4,3)
    number_habitable_rooms SMALLINT  (sourced from habitable_rooms in core_epc_domestic)
    bedrooms_estimated   SMALLINT  (= max(0, number_habitable_rooms - 1))
    total_floor_area     REAL
    current_energy_rating CHAR(1)

Expected match rates (verify after rebuild):
    SW1A 1AA: ~200/209 with EPC cert, ~149/209 with bedrooms
    CR5 1RA:  ~328/328 with EPC cert, ~259/328 with bedrooms
"""

import re
from datetime import date as dt_date

import psycopg2
import psycopg2.extras

from constants import SCHEDULE_MONTHLY, TABLE_NAMES

# ---------------------------------------------------------------------------
# Module metadata (read by pipeline.py)
# ---------------------------------------------------------------------------

METADATA = {
    "name":           "transactions_epc",
    "description":    "Bulk Jaccard address-match core_property_transactions × core_epc_domestic → core_transactions_epc.",
    "schedule":       SCHEDULE_MONTHLY,
    "depends_on":     ["epc_domestic", "land_registry"],
    "tables_written": [TABLE_NAMES["transactions_epc"]],
    "cache_key_patterns": ["pois:*"],
    "expected_row_range": (500_000, 10_000_000),
}

# ---------------------------------------------------------------------------
# Address normalisation
# ---------------------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^A-Z0-9 ]")


def _normalise_addr(s: str) -> set:
    """Uppercase, strip punctuation, return set of word tokens."""
    if not s:
        return set()
    return set(_NON_ALNUM.sub(" ", s.upper()).split())


def _jaccard(a: set, b: set) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ---------------------------------------------------------------------------
# Match logic (mirrors area.py _match_epc exactly)
# ---------------------------------------------------------------------------

def _best_match(tx_saon, tx_paon, tx_street, tx_date, epc_certs):
    """Find best EPC cert for a transaction. Returns (cert_row, match_score) or (None, None)."""
    tx_addr = _normalise_addr(" ".join(p for p in [tx_saon, tx_paon, tx_street] if p))
    if not tx_addr:
        return None, None

    candidates = []
    for c in epc_certs:
        epc_addr = _normalise_addr(
            " ".join(p for p in [c["address1"], c["address2"], c["address3"]] if p)
        )
        if not epc_addr:
            continue
        score = _jaccard(tx_addr, epc_addr)
        if score >= 0.5:
            candidates.append((score, c))

    if not candidates:
        return None, None

    if isinstance(tx_date, str):
        tx_date = dt_date.fromisoformat(tx_date)

    best = None
    best_score = None
    best_tiebreak = (-1, None)

    for score, c in candidates:
        ld = c["lodgement_date"]
        if ld is None:
            continue
        if isinstance(ld, str):
            ld = dt_date.fromisoformat(ld)
        before = ld <= tx_date
        days_diff = abs((tx_date - ld).days)
        tiebreak = (score, before, -days_diff)
        if best is None or tiebreak > best_tiebreak:
            best = c
            best_score = score
            best_tiebreak = tiebreak

    return best, best_score


# ---------------------------------------------------------------------------
# Main run function
# ---------------------------------------------------------------------------

def run(db_url: str) -> int:
    """
    Bulk match core_property_transactions × core_epc_domestic → core_transactions_epc.

    Strategy:
    1. Truncate core_transactions_epc.
    2. Process postcodes in batches: for each postcode, load all EPC certs and
       all transactions, run address matching, insert matched rows.
    3. Return final row count.
    """
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    print("  Truncating core_transactions_epc...", flush=True)
    cur.execute(f"TRUNCATE TABLE {TABLE_NAMES['transactions_epc']} CASCADE")
    conn.commit()

    # Get all distinct postcodes that exist in BOTH tables
    print("  Building postcode work list...", flush=True)
    cur.execute(
        f"""
        SELECT DISTINCT t.postcode
        FROM {TABLE_NAMES['property_transactions']} t
        WHERE t.postcode IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM {TABLE_NAMES['epc_domestic']} e WHERE e.postcode = t.postcode
          )
        ORDER BY t.postcode
        """
    )
    postcodes = [r["postcode"] for r in cur.fetchall()]
    print(f"  Found {len(postcodes):,} postcodes with both transactions and EPC certs", flush=True)

    total_matched = 0
    batch_size = 500   # postcodes per commit batch

    for batch_start in range(0, len(postcodes), batch_size):
        batch = postcodes[batch_start : batch_start + batch_size]

        # Load all EPC certs for this batch of postcodes
        cur.execute(
            f"""
            SELECT certificate_number, address1, address2, address3, postcode,
                   lodgement_date, total_floor_area, habitable_rooms, current_energy_rating
            FROM {TABLE_NAMES['epc_domestic']}
            WHERE postcode = ANY(%s)
            """,
            (batch,),
        )
        epc_by_postcode: dict = {}
        for row in cur.fetchall():
            pc = row["postcode"]
            if pc not in epc_by_postcode:
                epc_by_postcode[pc] = []
            epc_by_postcode[pc].append(dict(row))

        # Load all transactions for this batch of postcodes
        cur.execute(
            f"""
            SELECT transaction_id, postcode, saon, paon, street, date_of_transfer
            FROM {TABLE_NAMES['property_transactions']}
            WHERE postcode = ANY(%s)
            """,
            (batch,),
        )
        tx_rows = cur.fetchall()

        # Match and collect results
        result_rows = []
        for tx in tx_rows:
            pc    = tx["postcode"]
            certs = epc_by_postcode.get(pc, [])
            if not certs:
                continue

            best, score = _best_match(
                tx["saon"] or "", tx["paon"] or "", tx["street"] or "",
                tx["date_of_transfer"], certs,
            )
            if best is None:
                continue

            habitable  = best.get("habitable_rooms")
            habitable  = int(habitable) if habitable is not None else None
            bedrooms   = max(0, habitable - 1) if habitable is not None else None
            floor_area = best.get("total_floor_area")
            floor_area = float(floor_area) if floor_area is not None else None

            result_rows.append((
                tx["transaction_id"],
                best["certificate_number"],
                round(score, 3),
                habitable,
                bedrooms,
                floor_area,
                best.get("current_energy_rating"),
            ))

        if result_rows:
            psycopg2.extras.execute_values(
                cur,
                f"""
                INSERT INTO {TABLE_NAMES['transactions_epc']}
                    (transaction_id, certificate_number, match_score,
                     number_habitable_rooms, bedrooms_estimated, total_floor_area,
                     current_energy_rating)
                VALUES %s
                ON CONFLICT (transaction_id) DO UPDATE SET
                    certificate_number     = EXCLUDED.certificate_number,
                    match_score            = EXCLUDED.match_score,
                    number_habitable_rooms = EXCLUDED.number_habitable_rooms,
                    bedrooms_estimated     = EXCLUDED.bedrooms_estimated,
                    total_floor_area       = EXCLUDED.total_floor_area,
                    current_energy_rating  = EXCLUDED.current_energy_rating
                """,
                result_rows,
                page_size=1_000,
            )
            total_matched += len(result_rows)

        conn.commit()

        if (batch_start // batch_size) % 20 == 0:
            print(f"    Processed {batch_start + len(batch):,}/{len(postcodes):,} postcodes, "
                  f"{total_matched:,} matched so far", flush=True)

    # RealDictCursor returns dict rows; fetchone()[0] won't work — use a plain cursor
    plain_cur = conn.cursor()
    plain_cur.execute(f"SELECT COUNT(*) FROM {TABLE_NAMES['transactions_epc']}")
    count = plain_cur.fetchone()[0]
    cur.close()
    plain_cur.close()
    conn.close()
    print(f"  Final: {count:,} matched transactions", flush=True)
    return count

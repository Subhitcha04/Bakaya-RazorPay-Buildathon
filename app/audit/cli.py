"""
`make verify-audit` entrypoint. Prints CHAIN OK or the first broken
sequence number -- see PRODUCTION-ENGINEERING addendum §4.2 (rollback /
chain integrity). Exit code 0 = OK, 1 = broken, for CI wiring.
"""
from __future__ import annotations

import sys

from app.db import SessionLocal
from app.audit.ledger import verify_chain


def main() -> int:
    db = SessionLocal()
    try:
        ok, broken_seq = verify_chain(db)
        if ok:
            print("CHAIN OK")
            return 0
        print(f"CHAIN BROKEN at seq={broken_seq}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

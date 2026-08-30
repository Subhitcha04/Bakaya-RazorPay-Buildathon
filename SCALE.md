# Scale

This document is short because the honest answer is short:
**this project has not been load-tested, and this document does not
pretend otherwise.** See `HONEST_LIMITATIONS.md` item 12. What follows is
a real, verified account of the scale-relevant architectural choices
that exist in the code today, and an explicit list of what has and has
not been exercised.

## What has NOT been measured

- No throughput numbers (requests/second, cases/second)
- No latency percentiles under any load
- No behavior under concurrent write contention beyond what a single
  test process exercises serially
- No connection-pool sizing guidance based on actual measurement
- No measurement of the live dashboard API (`app/api/server.py`) under
  concurrent requests

## What IS real: scale-relevant architectural choices

### The outbox pattern is Postgres-only, and untested in the demo environment

`app/execution/outbox.py::claim_pending_batch()` uses
`FOR UPDATE SKIP LOCKED` so multiple worker processes can pull from the
same queue without blocking each other or double-claiming a row. This
is real, real SQL, and a correct pattern for concurrent worker scaling
under Postgres.

**It has never been exercised by this project's actual demo path.**
The module's own docstring states this directly: `FOR UPDATE SKIP
LOCKED` is Postgres-specific with no SQLite equivalent, so
`claim_pending_batch` "is not exercised by the SQLite smoke test."
Every seeded demo in this project (`scripts/seed_db.py`,
`bakaya.db`, the live dashboard) runs on SQLite. The concurrent-worker
claiming logic is real, committed code -- it has simply never been run
against the database engine it's written for.

What *is* tested regardless of database engine: the idempotency
guarantee the whole design depends on --
`InterventionAttempt.idempotency_key` as a UNIQUE constraint, which is
dialect-agnostic and is exercised directly (per the same module's
docstring, referencing its own chaos test).

### Real database indexes

19 indexed columns across the schema (`grep -rn "index=True" app/models/`),
covering every foreign key used in a hot lookup path: `case_id`,
`customer_id`, `merchant_id`, `trace_id`, `proposed_action_id`, plus
`AuditEntry.seq` and `AuditEntry.hash` specifically (relevant to the
hash-chain's own lookup pattern -- verifying a chain segment means
walking `seq`, not scanning the whole table). This is real schema
design for query performance, not a claim about measured query latency.

### Batch sizes actually run in this project

The largest population this project has actually generated in one run
is n=1000 (`run_batch.py`, `scripts/ablation_arms.py`, both default to
`--n 1000`) and n=200 for the seeded demo database
(`scripts/seed_db.py`). These numbers describe what was actually run,
not a tested ceiling -- there is no evidence one way or the other about
behavior at, say, n=100,000.

### SQLite's own real constraints

The live dashboard and every seeded demo run on SQLite, which has real,
well-known constraints relevant to any future scale claim: single
writer at a time (readers don't block, but concurrent writes serialize),
and no native support for `FOR UPDATE SKIP LOCKED` (above). A real
production deployment would need Postgres for the outbox pattern to
function as designed at all -- this isn't a "nice to have," the
concurrent-worker safety guarantee genuinely doesn't exist on SQLite.

## What this document does not do

- Estimate expected production throughput or latency -- no data exists
  to ground such an estimate honestly
- Recommend specific infrastructure sizing (server count, database
  tier) -- premature without the load-testing this document states
  hasn't happened
- Claim the architecture "will scale" -- the outbox pattern and indexed
  schema are reasonable, standard choices for the problem shape, and
  that is the strongest claim actually supportable here

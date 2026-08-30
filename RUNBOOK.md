# Runbook

Operational procedures for running, debugging, and recovering this system.
Every failure mode described below actually happened during this project's
own development -- these aren't hypothetical scenarios, they're documented
because they were real problems with real, verified fixes.

## Starting the system

```
python scripts/seed_db.py --n 200 --seed 20260901 --fresh
$env:DATABASE_URL = "sqlite:///./bakaya.db"     # PowerShell
uvicorn app.api.server:app --reload --port 8000
```

Second terminal:

```
cd frontend
npm install
npm run dev
```

See `README.md` for the full quickstart if this is the first run.

## Stopping the system cleanly

**Stop `uvicorn` before touching `bakaya.db` directly** (deleting it,
re-seeding, copying it). A running server holds a live connection pool
open against the SQLite file. On Windows specifically, attempting to
delete or overwrite a file with an open handle raises
`PermissionError: [WinError 32]` -- this is a real, hard OS-level rule on
Windows (POSIX permits deleting an open file; Windows does not), and it
was hit directly during this project's own development.

```
# Find what's holding the file
Get-Process python,uvicorn -ErrorAction SilentlyContinue
# Stop it
Stop-Process -Id <PID> -Force
```

Only then re-seed:

```
Remove-Item .\bakaya.db -Force -ErrorAction SilentlyContinue
python scripts\seed_db.py --n 200 --seed 20260901 --fresh
```

## Re-seeding the database

`scripts/seed_db.py --fresh` deletes the existing `bakaya.db` and rebuilds
from scratch. Without `--fresh`, it adds to whatever's already there.
`--seed` controls reproducibility -- the same seed value always produces
byte-identical `RiskCase` and `Diagnosis` rows (confirmed via a direct
exact-ID comparison across two independent runs, not just aggregate
counts). Changing `--n` changes case volume but not the underlying
per-cause routing logic.

## Common failure modes and their real fixes

### "PermissionError: The process cannot access the file" (Windows, SQLite)

Covered above. General rule: any script or test that opens a SQLite
engine must call `.close()` on the session and `.dispose()` on the
engine before the file can be deleted on Windows. This was a real bug
found in `scripts/seed_db.py` and in this project's own test helpers,
fixed with explicit `close()`/`dispose()` calls
(`tests/test_seed_db.py`'s `_cleanup()` helper is the reference pattern).

### `python scripts/compare_llm_diagnosis.py` fails with a 429 rate-limit error

Groq's free tier caps token throughput. The script already paces calls
with a 9-second delay by default (`DEFAULT_DELAY_SECONDS`) and retries
with exponential backoff on a 429
(`MAX_RETRIES_ON_RATE_LIMIT = 5`). If it still fails, you're on a
lower-than-expected tier limit -- increase the delay:

```
python scripts/compare_llm_diagnosis.py --delay 15
```

### `.env` values aren't loading into the PowerShell session

Two real causes hit during this project:

1. **Byte-order-mark corruption.** A `.env` file saved with a UTF-8 BOM
   (common when created via some editors or `Set-Content -Encoding UTF8`
   in older PowerShell) attaches an invisible character to the first
   line's variable name, so `GROQ_API_KEY` silently becomes
   `"\uFEFFGROQ_API_KEY"` and is never found. Fix: strip the BOM
   explicitly when loading:

```
Get-Content .env | ForEach-Object {
    $line = $_.Trim([char]0xFEFF).Trim()
    if ($line -match '^([^=]+)=(.*)$') {
        Set-Item -Path "Env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}
```

2. **Session scope.** Environment variables set this way apply only to
   the current PowerShell session. A new terminal window needs the
   loader run again.

### Copy-pasting a large file into PowerShell corrupts or truncates it

Hit repeatedly during this project with large markdown files: em-dashes
and other non-ASCII characters can get mis-decoded through a copy/paste
or editor round-trip, showing up as mangled multi-byte replacement
characters where a real em-dash should be. Separately, very large
here-string pastes can silently truncate partway through with no error
at all. The reliable fix used throughout this project: write files as
pure ASCII (no em-dashes, no smart quotes) and transfer via base64:

```
# On the source side:
base64 -w0 file.md
# On the Windows side:
$b64 = "<paste>"
[System.IO.File]::WriteAllBytes("file.md", [System.Convert]::FromBase64String($b64))
```

Also worth knowing: `(Get-Content file.md | Measure-Object -Line).Lines`
undercounts blank lines (each blank line contributes 0 to the count
instead of 1, since `Get-Content` already splits the file into
newline-free strings). Use `[System.IO.File]::ReadAllLines("file.md").Count`
instead for an accurate line count.

### A test that should be deterministic fails intermittently

Check whether the test constructs a `DiagnosticInput` (or similar) with
`case_id` left to a random default rather than an explicit, fixed value.
Diagnosis for causes without real Tier-1 coverage falls through to
`TEACHER_STUB`, which is deterministic *given a fixed `case_id`* (it
hashes `case_id` to make its pseudo-random choice) -- a randomly
generated `case_id` breaks reproducibility even though the underlying
logic is fully deterministic. This exact bug was found and fixed in
`scripts/seed_db.py` (`RiskCase`/`Customer` rows were getting random
UUIDs instead of the synthetic generator's deterministic IDs).

## Rollback (`app/mlops/rollback.py`)

`rollback(db, component)` flips a component's status and writes an audit
entry -- used to revert a model version or a policy component if a
regression is detected post-deployment. Raises `RollbackError` if no
live version exists for the given component, rather than silently
no-op-ing.

## Shadow evaluation (`app/mlops/shadow.py`)

`run_shadow_comparison()` compares two decision-producing implementations
(e.g. the stub vs. a candidate model) against the same inputs without
either one actually executing anything -- the mechanism this project's
`scripts/compare_llm_diagnosis.py` is a specific instance of, generalized
for any two comparable decision sources.

## Drift detection (`app/mlops/drift.py`)

`compute_psi()` computes Population Stability Index between a baseline
and current distribution over categorical values (e.g. root-cause
frequencies), returning a `DriftReport`. Not currently wired to any
automated alert or scheduled job in this codebase -- it's a real,
callable function, not yet an operational monitor.

## Replay (`app/api/replay.py`)

`replay_case(db, case_id)` reconstructs the most recent proposal and
policy decision for a case, read-only -- no gates are re-evaluated, no
new rows are written. This is what backs `evaluate_only()`'s dry-run
inspection path (`ARCHITECTURE.md` decision 6) and what the case-detail
API endpoint effectively does when it reads a case's `AuditEntry` for
display.

## What this document does not cover

- Production deployment topology, container orchestration, or
  infrastructure-as-code -- none of that exists in this project yet
- Alerting or on-call procedures -- `app/observability/metrics.py`
  defines real metric names and SLO thresholds, but nothing is wired to
  page anyone
- Database migrations -- schema changes in this project have so far
  meant re-running `Base.metadata.create_all()` against a fresh SQLite
  file, not a real migration tool

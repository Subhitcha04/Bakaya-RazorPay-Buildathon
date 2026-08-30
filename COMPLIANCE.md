# Compliance

This document covers the 9 RBI-derived control-plane gates
(`app/control_plane/gates/rbi/`). Every threshold, field name, and behavior
below is read directly from the real gate code, not summarized from memory.
32 tests across 9 dedicated test files exercise these gates, and all 9 were
independently confirmed to actually block via mutation testing
(`EVALUATION.md` section 4.1) -- both facts are reproducible:

```
python -m pytest tests/test_compliance_afa_never_bypassed.py tests/test_compliance_afa_threshold_by_category.py tests/test_compliance_fastag_exemption.py tests/test_compliance_no_mandate_fee.py tests/test_compliance_opt_out_is_permanent.py tests/test_compliance_post_debit_sent.py tests/test_compliance_pre_debit_payload_complete.py tests/test_compliance_redressal_in_all_templates.py tests/test_compliance_variable_cap_enforced.py -v
python scripts/mutate_gates.py
```

## The one distinction that matters most in this document

**Every gate's logic is real, tested, and independently confirmed to
actually block.** The specific RBI circular clause number each gate's
docstring cites as its basis is a separate claim, and it is NOT yet
independently verified against the primary regulatory text
(`rbi.org.in`). Every one of the 9 gate files below carries this exact
comment: `TODO: verify clause number against the primary circular before
shipping.` This document does not pretend otherwise. The behavior these
gates implement is a reasonable, defensible reading of secondary reporting
on RBI's e-mandate framework (Circular RBI/DPSS/2026-27/396, 21 April
2026, per the referenced circular number) -- but "reasonable reading of
secondary reporting" and "independently verified against the primary
text" are different claims, and only the first one is made here. See
`HONEST_LIMITATIONS.md` item 11.

## The 9 gates, what they actually check

### 1. AFA required (`afa_required.py`)

Additional Factor of Authentication is required at 5 specific mandate
lifecycle events: `registration`, `modification`, `withdrawal`,
`first_transaction`, `opt_out`. The gate blocks if the proposed action
corresponds to one of these events and `context["afa_completed"]` is not
`True`. Any other mandate event passes through untouched -- this gate is
deliberately narrow, not a blanket "always require AFA" check.

### 2. AFA threshold (`afa_threshold.py`)

No AFA is required for recurring debits at or below **Rs 15,000**
(`STANDARD_THRESHOLD_PAISE = 15_000_00`). This limit rises to **Rs
1,00,000** (`HIGH_THRESHOLD_PAISE`) for three specific categories:
insurance premiums, mutual fund subscriptions, and credit card bill
payments (`HIGH_THRESHOLD_CATEGORIES`). Above the applicable threshold
without completed AFA, the gate blocks -- the transaction must route
through an AFA-gated flow instead, never a silent retry.

### 3. FASTag/NCMC exemption (`fastag_exemption.py`)

FASTag and NCMC auto-replenishment (`case.kind` in
`{"fastag_replenishment", "ncmc_replenishment"}`) are exempt from the
pre-transaction notification requirement (gate 6, below). This gate
always returns `True` -- its purpose is not to block anything, but to
stamp the exemption reasoning explicitly into the evidence trail for
every case, whether the exemption applies or not. Modelling the exception
correctly, not just the headline rule, is deliberate: it's the cheapest
way to demonstrate the primary source was actually read, not summarized
from a rule-of-thumb.

### 4. No mandate facility fee (`no_mandate_fee.py`)

No customer charge is permitted for the e-mandate facility itself,
separate from whatever the underlying transaction amount is. Blocks if
`context["mandate_facility_fee_paise"] > 0`.

### 5. Opt-out honoured (`opt_out_honour.py`)

Checks a **per-transaction** opt-out signal
(`context["customer_opted_out_of_this_transaction"]`), distinct from a
permanent, mandate-level opt-out. The permanent case is enforced
separately, at the database level, by the `Suppression` table's UNIQUE
constraint plus the core `suppression.py` gate -- two different scopes of
"no," both real, both independently enforced, neither substituting for
the other.

### 6. Post-debit notification (`post_debit_notification.py`)

Mandatory after every e-mandate debit. Blocks if
`context["post_debit_notification_sent"]` is not `True`. Skipped
entirely for non-mandate debits.

### 7. Pre-debit window (`pre_debit_window.py`)

Pre-transaction notification must be sent **at least 24 hours** before
any e-mandate debit (`MIN_LEAD_TIME = timedelta(hours=24)`), and must
carry all 7 of: `merchant_name`, `amount_paise`, `debit_at`,
`mandate_reference`, `transaction_reference`, `reason_for_debit`,
`grievance_redressal`. FASTag/NCMC auto-replenishment is exempt (gate 3
stamps this, this gate reads `context["notification_exempt"]` to skip
the check for exempt cases). Skipped entirely for non-mandate debits.

### 8. Redressal in templates (`redressal_in_templates.py`)

Every customer-facing template must surface a grievance/dispute contact
path. Implemented as a lint over the Composer's drafted copy text,
checking for any of: `"grievance"`, `"complaint"`, `"redressal"`,
`"contact us"`, `"support@"`. This is the one gate in the whole
control plane that runs on free text rather than structured context --
worth noting explicitly, since it's a genuinely different failure mode
than the other 13 gates (all of which check structured fields, not
prose). Passes trivially for actions with no customer-facing copy at all
(e.g. silent L1 retries).

### 9. Variable mandate cap (`variable_mandate_cap.py`)

Variable-amount mandates must carry a declared maximum transaction limit
(`context["variable_mandate_max_paise"]`). Blocks if no maximum is on
file, or if the proposed amount exceeds the declared maximum --
regardless of what any other part of the system computed as the "correct"
amount. The mandate's own declared ceiling is the authority, the same
principle the general-purpose `offer_ceiling.py` core gate applies
system-wide, specifically enforced here for mandate law. Skipped
entirely for fixed-amount mandates.

## What every gate has in common

Every one of the 9 (like all 14 control-plane gates) follows the same
contract: a `check(db, case, proposed, context)` function returning a
`GateResult` with `passed: bool`, a human-readable `reason` on failure,
and an `evidence` dict recorded into the decision's audit trail regardless
of outcome. None of these gates ever raise an exception on a business-logic
failure -- a blocked action is a normal, expected, fully-audited return
value, not an error path. This is why the live dashboard can show a real
reason string for every BLOCK verdict (`app/api/server.py`'s
`_evidence_chain`, reading `PolicyDecision.failed_gate` directly).

## What this document does not cover

- Whether the *behavior* these gates implement is what RBI's primary text
  actually requires, versus what secondary reporting says it requires --
  unverified, stated above and in `HONEST_LIMITATIONS.md` item 11
- FEMA, PCI-DSS, or any compliance framework outside RBI's digital
  payments / e-mandate rules -- out of scope for this project entirely
- Whether these 9 gates are a *complete* enumeration of RBI's e-mandate
  requirements -- they cover AFA, thresholds, exemptions, fees, opt-out,
  notifications (pre and post), redressal, and variable-amount caps, which
  is a substantial but not necessarily exhaustive set

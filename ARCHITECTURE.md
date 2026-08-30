# Architecture

Every claim below is checkable against a specific file. Where this document
says "N gates" or "5 agents," that number comes from counting real files or
real dict entries, listed explicitly below, not from memory or estimation.
See `README.md` for how to run any of this; `EVALUATION.md` for what's been
measured; `HONEST_LIMITATIONS.md` for what hasn't.

## The core principle

**The model's belief about what it's authorized to do is never the
credential.** Every proposal from the Decision plane is independently
re-derived and re-checked by the Control plane before anything real
happens. This single rule is why the red-team suite (15 attacks) and the
adversarial-policy test (20 attacks, a synthetic policy deliberately trying
to breach every guardrail at once) both report zero successes
(`EVALUATION.md` section 4) -- an attacker who fully controls the free-text
input, or even a compromised/buggy proposer, still cannot get an
unauthorized action past a gate that never trusted the proposal to begin
with.

## Three planes, strictly separated

```
DECISION PLANE                CONTROL PLANE              EXECUTION PLANE
(the only place an             (100% deterministic,       (real channel
 LLM is ever consulted,         zero LLM, independently    adapters, real
 and even then, not by          re-derives every           audit trail)
 default -- see below)          authorization decision)

Detector                       14 gates                   Outbox
   v                           (5 core + 9 RBI)            (FOR UPDATE
Diagnostician                     v                         SKIP LOCKED)
(2-tier, see below)            mint_capability()              v
   v                              v                        Channel
Strategist                     CapabilityToken             adapters
   v                           (single-use, case-scoped,   (email real;
Composer                        5-min TTL, ceiling          whatsapp/sms/
   v                            independently computed)     voice simulated)
Critic                            v                            v
                                AuditEntry                  Razorpay
                                (hash-chained,               client
                                 append-only)                (verified live,
                                                              EVALUATION.md
                                                              section 3.2)
```

## Decision plane

### The 5 real agents (`app/agents/`)

`composer.py`, `critic.py`, `diagnostician.py`, `strategist.py`. (`taxonomy.py`
and `llm_client.py` in the same directory are shared data/infrastructure, not
agents themselves -- 5 agents, not 6 or 7, deliberately: an earlier design
consideration split diagnosis into more steps, but that was judged
over-decomposition for what this system actually needs to decide.)

### Diagnostician: 2 tiers, real cost-cascade discipline

- **Tier 1** (`_tier1_lookup` in `diagnostician.py`): a deterministic
  dictionary lookup keyed on Razorpay's real `error_reason` field
  (`taxonomy.py::ERROR_REASON_TO_ROOT_CAUSE`, 25 real entries, 7 of 8 root
  causes covered -- see `EVALUATION.md` section 1 for the full accuracy
  breakdown). Free, instant, ~97% confidence by construction.
- **Tier 2**: only reached when Tier 1 can't resolve confidently. Two
  interchangeable implementations behind the same interface:
  - `TEACHER_STUB` -- the DEFAULT. A free, deterministic keyword matcher.
    Never claims to be a real model.
  - `call_llm_diagnostician` -- REAL, verified against a live Groq account
    (`EVALUATION.md` section 2). **Never invoked automatically** by
    `diagnose()` -- this is enforced by two tests
    (`test_diagnose_never_calls_the_llm_even_with_a_key_in_the_environment`,
    a source-inspection test that greps `diagnose()`'s actual source for
    any reference to the live function). Only
    `scripts/compare_llm_diagnosis.py` invokes it, explicitly.

This is the concrete implementation of "the biggest cost lever is not
calling the LLM at all" -- Tier 1 resolves the majority of cases for zero
model cost, and the live-LLM path exists and works but is opt-in, not
default.

### Strategist and the ladder

The Strategist maps a diagnosed root cause to an entry point on a 7-level
ladder (`app/control_plane/stopping_rules.py::LadderLevel`):

| Level | Meaning |
|---|---|
| L0 | Prevent (pre-debit notification) |
| L1 | Silent retry (max 3 attempts) |
| L2 | Passive surface (no direct contact) |
| L3 | Nudge -- single attempt, no escalating offer sequence |
| L4 | Assisted -- channel + offer, max 2 attempts |
| L5 | Human queue -- never autonomous |
| L6 | Terminal |

Real entry-level routing (`app/ladder/levels.py::ROOT_CAUSE_TO_ENTRY_LEVEL`):

```
insufficient_funds  -> L1   (silent retry -- timing-modelled)
gateway_timeout     -> L1   (transient, retry immediately, silent)
issuer_risk_decline -> L1   (try once silently, then escalate)
customer_intent     -> L2   (passive first -- never nudge on first abandonment)
expired_card        -> L3   (not silently recoverable -- needs a nudge)
mandate_lapsed      -> L3   (re-auth link required)
fraud_flag          -> L5   (never autonomous -- straight to human)
other               -> L5   (unknown cause -- don't guess, escalate)
```

Any root cause not in this table falls back to `DEFAULT_ENTRY_LEVEL = L5` --
the fail-safe default routes to a human, never to a silent autonomous
action. This is a deliberate asymmetry: an unmapped cause is treated as the
riskier case, not the safer one.

### Composer and Critic

Composer fills fixed, pre-approved templates with case-specific numbers --
it does not freely generate customer-facing copy. Every template includes a
redressal/support contact line, checked by the real `redressal_in_templates`
RBI gate (see below) for any AI-composed message. Critic performs a
decision-plane quality check (tone, internal consistency, RBI clause
references) before a proposal is persisted -- deliberately skipped by
`scripts/seed_db.py` for simplicity (`HONEST_LIMITATIONS.md` item 6), but
real and tested in the core pipeline.

## Control plane

### 14 real gates, every one independently confirmed to actually block

5 core gates (`app/control_plane/gates/`): `calling_window.py`, `consent.py`,
`frequency_cap.py`, `offer_ceiling.py`, `suppression.py`.

9 RBI-derived gates (`app/control_plane/gates/rbi/`): `afa_required.py`,
`afa_threshold.py`, `fastag_exemption.py`, `no_mandate_fee.py`,
`opt_out_honour.py`, `post_debit_notification.py`, `pre_debit_window.py`,
`redressal_in_templates.py`, `variable_mandate_cap.py`.

Every one of these 14 was individually disabled and the full test suite
re-run to confirm at least one test catches the regression -- this found
two real, previously-uncovered gaps (`consent`, `calling_window`), which
were fixed. Current state: 14/14 mutations caught (`EVALUATION.md`
section 4.1, reproduce with `python scripts/mutate_gates.py`). The specific
RBI circular clause each of the 9 RBI gates claims to implement carries an
explicit unverified-citation TODO -- the gate *logic* is real and tested,
the specific clause reference is not yet independently checked
(`HONEST_LIMITATIONS.md` item 11).

### Capability tokens, not role-based access control

`app/control_plane/capability.py::mint_capability()` is the only function
that authorizes a money-moving action. A `CapabilityToken`
(`app/models/decision.py`) is:

- **Single-use** (`used: bool`, flipped on first execution, checked before
  every use)
- **Case-scoped** (`case_id` foreign key, cannot authorize a different case)
- **Time-bounded** (`expires_at`, a 5-minute TTL)
- **Independently ceilinged** (`max_amount_paise` is computed by the gate
  logic itself from merchant/customer state, never copied from what the
  Strategist proposed)
- **Versioned** (`policy_version`, so a token minted under an old policy
  can't silently authorize a check made under a newer one)

This was a deliberate choice over group-based RBAC: a role check answers
"is this caller generally allowed to do this class of thing," which says
nothing about this specific case, this specific amount, right now. A
capability token answers the narrower, correct question.

### The audit ledger is hash-chained, not just logged

`app/models/audit.py::AuditEntry` -- every row carries `prev_hash` and its
own `hash`, appended only via `audit/ledger.py::append()`, never updated or
deleted. `event_type` covers `grant`, `block`, `escalate`, `execute`,
`refuse` -- **refusals are audited as rigorously as approvals.** This is
what lets the live dashboard's case-detail view show a real SHA-256 hash
for both ALLOW and BLOCK verdicts (`app/api/server.py::_grant_or_block_hash`),
and what the adversarial-policy test checks explicitly: all 20 attack
refusals are independently confirmed audited, not silently dropped
(`test_greedy_every_refusal_is_actually_audited_not_silently_dropped`).

## Execution plane

### Detectors: 6 surfaces, 2 deliberately never execute

`app/detectors/`: `payment_failure.py`, `checkout_abandonment.py`,
`mandate_failure.py`, `receivables.py` all set `EXECUTES = True`.
`churn_intent.py` and `cohort_degradation.py` both set `EXECUTES = False` --
hardcoded, not derived from any runtime condition. These two surfaces
detect a signal worth surfacing (a customer showing churn intent, a cohort
degrading) but are deliberately never wired to an autonomous action; the
constant is the whole safety mechanism. Checked by
`test_churn_intent_always_executes_false_no_matter_what` (an adversarial
test that feeds every payload field that might tempt a naive implementation
into deriving `executes` from content instead of the hardcoded constant --
`tests/test_detectors.py`), and by an inline `executes is False` assertion
within `test_cohort_degradation_flags_significant_drop_with_enough_samples`
in the same file.

### Outbox pattern, not a task queue

Execution goes through a Postgres/SQLite outbox table processed with
`FOR UPDATE SKIP LOCKED` rather than a separate task-queue system (e.g.
Celery) -- chosen for atomicity: the outbox row is written in the same
transaction as the decision that created it, so there is no window where a
decision is recorded but the corresponding action is lost or duplicated
because a separate queue never received it.

### Channel adapters: 1 real, 3 simulated

Email sends through a genuine SMTP path (`app/execution/`); WhatsApp, SMS,
and voice are simulated adapters with the same interface. This is stated
directly in the honesty table in `EVALUATION.md` section 1's neighbor --
`README.md`'s "what's real vs simulated" table.

### Razorpay client: real, verified against live infrastructure

`app/execution/razorpay_client.py` -- auth, retry-with-backoff, and a real
create+fetch round trip against Razorpay's Payment Links API, confirmed
live (`EVALUATION.md` section 3.2). Field shapes verified against
Razorpay's own API reference, not invented.

## Data model

18 SQLAlchemy tables (`app/models/`): `Merchant`, `Customer`, `Consent`,
`Suppression`, `RiskCase`, `FailureEvent`, `Diagnosis`, `ProposedAction`,
`PolicyDecision`, `CapabilityToken`, `InterventionAttempt`, `Outcome`,
`AuditEntry`, `CostEntry`, `Experiment`, `ContactBudgetLedger`,
`ModelVersion`, `InboundEvent`. Note: `InterventionAttempt` and `Outcome`
are real tables with real schemas, but are not currently populated by
`scripts/seed_db.py` -- see `HONEST_LIMITATIONS.md` item 5 for exactly
what that means for the live dashboard.

## Key architecture decisions, stated with reasoning

1. **Outbox over a task queue** -- atomicity with the decision transaction
   (see above).
2. **Capability tokens over role-based access control** -- a role check
   can't express "this case, this amount, right now" (see above).
3. **5 agents, not more** -- an earlier design considered splitting
   diagnosis into further steps; judged over-decomposition relative to
   what actually needs a separate decision point.
4. **`EXECUTES` as a hardcoded constant, not a runtime flag** -- for
   `churn_intent` and `cohort_degradation`, making autonomy a compile-time
   constant rather than a configurable setting means there is no code path,
   config value, or environment variable that could silently turn
   execution on for these two surfaces.
5. **Silent-first ladder** -- L0/L1 involve zero customer contact and zero
   channel cost; only L3+ ever reaches the customer directly. This
   ordering is itself a cost and annoyance-minimization decision, not
   arbitrary.
6. **`dry_run=True` on capability evaluation, kept separate from minting**
   -- `evaluate_only()` (`app/control_plane/capability.py`) lets replay and
   dashboard-detail code inspect what a decision *would* be without ever
   writing a token or audit row -- a debugging/inspection tool must not be
   able to alter the record it's reading.
7. **`MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT = 0.85`, set from measurement**
   -- raised from an initial 0.55 after the calibration report
   (`EVALUATION.md` section 4.4) showed the 0.4-0.8 confidence range was
   badly overconfident (9.1%-18.2% actual accuracy). Not a round number
   chosen for its own sake.
8. **RAG explicitly not used** -- policy/compliance lookups in this system
   are deterministic dictionary/gate checks, not retrieved-and-reasoned-over
   text. Adding a retrieval step would trade a correct, auditable lookup
   for a probabilistic one, with no offsetting benefit for content this
   structured.
9. **Field names in `DiagnosticInput` match Razorpay's real Payment entity**
   -- `error_code`, `error_reason`, `error_source`, `error_step`,
   `error_description` are not an internal invention; they mirror the flat
   fields Razorpay's own webhook payloads actually carry
   (`app/agents/diagnostician.py`'s module docstring cites the exact
   Razorpay doc pages this was checked against).

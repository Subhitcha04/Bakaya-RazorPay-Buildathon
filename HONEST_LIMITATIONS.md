# Honest Limitations

This document exists so nothing here has to be discovered by a skeptical
reader instead of stated upfront. Every limitation below is real and current
as of this writing -- not hedging, not false modesty. See EVALUATION.md for
what's actually been measured; this is what hasn't, and why.

---

## 1. No live merchant -- every recovery-outcome number is simulated

The single biggest limitation of this whole project. Every gate, every audit
entry, and Tier-1 diagnosis are real and verified (EVALUATION.md section 1).
Whether an intervention actually recovers money is not -- it comes from
`sim/response_model.py`'s calibrated priors, because a student project
cannot obtain a real merchant with real transaction volume before the
deadline. The 4 recovery-lift numbers in EVALUATION.md section 3 (the
batch result, the oracle ceiling, the ablation, the stability sweep) all
inherit this limitation and are reported with the caveat attached every
time, not once at the top and then forgotten.

## 2. The diagnosis LLM is not in the default path

`call_llm_diagnostician` is real, tested against live Groq infrastructure,
and measurably more accurate than the deterministic stub (94.0% vs 64.0%,
EVALUATION.md sections 1-2). But `diagnose()` -- the function every other
part of the system actually calls -- never invokes it automatically, by
design, so the whole test suite and the seeded database stay reproducible
without an API key. This means the 94.0% figure describes a path that is
not exercised by default anywhere in this codebase except the one
comparison script that explicitly turns it on. A real deployment decision
about whether to make the LLM path the default has not been made, and this
document is not making it either.

## 3. Real Razorpay reasons with no clean home in the taxonomy

`taxonomy.py::AMBIGUOUS_REASONS` lists a representative, explicitly
non-exhaustive sample of real Razorpay `error_reason` values that don't map
cleanly onto any of the 8 root causes (`incorrect_cvv`, `card_not_enrolled`,
`transaction_limit_exceeded`, `invalid_vpa`, and others). Razorpay documents
roughly 90 distinct reason values across their Bad Request and Gateway
Errors tables; this codebase explicitly maps 25 of them and lists about 13
more as a documented ambiguous sample. The rest -- business/integration
errors like `invalid_amount`, `order_already_paid`, `live_mode_not_enabled`
-- are not customer payment-failure causes at all and were deliberately
left out of the taxonomy entirely, not overlooked. Anything not explicitly
listed falls through to Tier 2 safely (no crash, no misclassification into
a wrong bucket), but the mapping table is a representative sample of
Razorpay's real vocabulary, not a complete enumeration of it.

## 4. `TEACHER_STUB` cannot classify hint-less `customer_intent` text

A structural limitation of the free, deterministic stub, not the
architecture. Pinned exactly by `test_documented_customer_intent_recall_
mechanism`: of 6 golden-set cases, 2 resolve via real Tier 1, 1 via a
lucky keyword match, and 3 are permanently unresolvable by a keyword-only
classifier because `customer_intent` was never added to the stub's
ambiguous-fallback candidate list. Adding it would require either expanding
the stub's keyword list (which only pushes the same limitation to
differently-worded hint-less text) or switching the default path to the
LLM (see limitation 2).

## 5. No `InterventionAttempt` or `Outcome` rows are persisted

`scripts/seed_db.py` seeds through Detected -> Diagnosed -> Decided ->
Authorized. It does not persist whether an authorized action was actually
sent, or whether the customer paid as a result. The live dashboard's
case-detail view (`app/api/server.py`) reflects this honestly: the evidence
chain for an ALLOW case stops at 4 real steps, not 7, and `recoveredPaise`
is always `null` in the API response -- not because the field is broken,
but because there is no real value to put there yet. This is a stated
scope boundary, documented in the seed script's own module docstring, not
a bug discovered after the fact.

## 6. Critic review is skipped during seeding

`scripts/seed_db.py` does not run the Critic agent -- it's a decision-plane
quality check (verifying a proposal's tone, RBI clause references, and
internal consistency before persistence), not required for control-plane
authorization, and was left out of the seed script deliberately to keep it
simpler. This means seeded `ProposedAction` rows have not been through the
same review step a fully-live case would go through before being sent.

## 7. Webhook signature verification has never seen a real Razorpay signature

`webhooks/router.py`'s HMAC verification logic is tested against a
hand-constructed signature (`webhook_test.py`), proving the verification
*logic* is correct. It has never been exercised against a signature
Razorpay's own servers actually generated, because that requires a
publicly reachable endpoint (e.g. via ngrok) receiving a real webhook
delivery -- not yet done. Given the real, confirmed surprises found simply
by making a live Razorpay API call (EVALUATION.md section 2.2), it would be
unwise to assume this path has no equivalent surprise waiting.

## 8. The golden set is small

50 hand-constructed cases, unevenly split across 8 classes (6-7 per class).
The calibration bands reported in EVALUATION.md section 4.4 are built on
buckets of 10, 11, and 29 cases respectively -- real numbers, but not a
statistically powerful sample. A single relabeled or added case could move
a per-class recall figure by double-digit percentage points. Every number
derived from this set should be read as "measured on 50 specific cases,"
not as a confident estimate of population-level accuracy.

## 9. `WRONG_LEVEL_CORRECTNESS = 0.35` is illustrative, not measured

Used by `app/ladder/random_policy.py` for the `exhaustive_random` ablation
arm (EVALUATION.md section 3.2). This value represents "how often a
randomly-chosen ladder level happens to still work reasonably well" and was
never independently measured -- it's a reasonable, stated assumption, not
data. The 48.4%-attributable-to-judgment finding in the ablation depends on
this constant; a different, equally defensible choice of value would move
that headline percentage.

## 10. Approval-queue actions do not persist

The frontend's Approve/Reject/Compose & send buttons
(`frontend/src/screens/ApprovalQueue.tsx`) dismiss a card from view
client-side only. There is no `POST /api/approvals/{id}/send` endpoint or
equivalent backend mutation yet -- a human's decision in the UI is not
recorded anywhere. This was true even against the original mock data and
was never claimed to be otherwise, but is worth restating now that the UI
is wired to genuinely real case data, where the gap is easier to miss.

## 11. RBI compliance gate clause numbers are unverified

All 9 RBI-derived control-plane gates (`app/control_plane/gates/rbi/`)
carry an explicit `TODO: verify clause number against the primary circular
before shipping` comment. The gates' *logic* is real and tested (pre-debit
window timing, AFA thresholds, opt-out honouring, and so on all actually
run and actually block), but the specific RBI circular clause each gate
claims to implement has not been independently checked against the primary
regulatory text. The behavior is defensible and reasonable; the citation
is not yet verified.

## 12. No load or scale testing

Every performance claim in this codebase is either absent or purely
architectural (e.g. "the outbox pattern uses `FOR UPDATE SKIP LOCKED` for
safe concurrent processing"). Nothing has been measured under concurrent
load -- no throughput numbers, no latency percentiles, no behavior under
contention beyond what the unit tests exercise serially. `SCALE.md`
states this directly rather than estimating a throughput number
that doesn't exist.

## 13. Compliance draft templates in the frontend bypass the real gate

The Approval Queue's per-case-reason draft templates
(`draftTemplateFor()` in `ApprovalQueue.tsx`) are a frontend convenience
for a human writing an ad-hoc message where no AI-composed draft exists
(see limitation 5's neighbor: fraud_flag/other cases never get a
Strategist-proposed channel or copy at all). These drafts are NOT checked
by the real `redressal_in_templates` compliance gate the way a
Composer-generated template is -- there is no server-side validation of a
human-authored message before it would theoretically be sent. A real
implementation would want the same gate applied to this path.

## 14. `sim/response_model.py`'s calibration sources are a best-effort estimate

The simulator's baseline recovery rates and per-cause uplift priors
(`sim/calibration_sources.md`) were assembled from public benchmarks and
reasonable estimation, not from a real merchant's historical data, since
none exists for this project. Every number downstream of this file
(everything in EVALUATION.md section 3) inherits this uncertainty. The
simulator is internally consistent and its own ground truth is fully known
(which is what makes the oracle-ceiling calculation possible at all), but
"internally consistent" and "reflects real customer behavior" are
different claims, and only the first one is made here.

## 15. Single-merchant, single-scale demo

`scripts/seed_db.py` seeds one demo merchant with one spend cap
(Rs 50,000/day) and one offer ceiling configuration. Nothing has been
tested against a merchant with meaningfully different transaction volume,
different LTV distribution, or different risk tolerance. The architecture
is designed to be per-merchant configurable (`Merchant.spend_cap_paise_
daily` is a real column, not hardcoded), but that configurability has
never actually been exercised with a second, differently-configured
merchant.

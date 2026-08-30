# Calibration sources for the reality generator

Every distribution in `reality_generator.py` and `response_model.py` is either:

1. A **structural mapping** traceable to Razorpay's own documented surfaces
   (`SURFACE_BY_CAUSE`), or
2. An **illustrative prior** drawn from published vendor claims (Stripe,
   Chargebee, Recurly blog posts on smart-retry / dunning recovery rates),
   used only to give the simulator a plausible shape.

These priors are not measured from real transactions and must never be
presented in the README or the pitch video as real-world benchmarks this
system achieved. See EVALUATION.md for the required disclosure.

| Parameter | Source type | Notes |
|---|---|---|
| ROOT_CAUSE_WEIGHTS | Illustrative prior | Shape only, unvalidated |
| BASELINE_RECOVERY_RATE | Illustrative prior | Vendor-blog order of magnitude |
| INTERVENTION_UPLIFT | Illustrative prior, deliberately includes one negative value (sleeping dog) | Not measured |

TODO before the pitch: replace this table's "illustrative prior" rows with
citations to the specific vendor sources once selected.

from dataclasses import dataclass

from app.mlops.shadow import run_shadow_comparison


@dataclass
class FakeCase:
    id: str
    root_cause: str


@dataclass
class FakeDecision:
    ladder_level: str
    channel: str | None
    amount_paise: int


def _live_decide(case: FakeCase) -> FakeDecision:
    return FakeDecision(ladder_level="L3", channel="email", amount_paise=0)


def _shadow_agrees_decide(case: FakeCase) -> FakeDecision:
    return FakeDecision(ladder_level="L3", channel="email", amount_paise=0)


def _shadow_diverges_decide(case: FakeCase) -> FakeDecision:
    if case.root_cause == "high_value":
        return FakeDecision(ladder_level="L4", channel="whatsapp", amount_paise=5000)
    return FakeDecision(ladder_level="L3", channel="email", amount_paise=0)


def test_full_agreement_gives_rate_1_and_no_divergences():
    cases = [FakeCase(id=f"c{i}", root_cause="insufficient_funds") for i in range(5)]
    report = run_shadow_comparison(cases, _live_decide, _shadow_agrees_decide)
    assert report.total == 5
    assert report.agreements == 5
    assert report.agreement_rate == 1.0
    assert report.divergences == []


def test_partial_divergence_computed_correctly():
    cases = [
        FakeCase(id="c1", root_cause="insufficient_funds"),
        FakeCase(id="c2", root_cause="high_value"),
        FakeCase(id="c3", root_cause="insufficient_funds"),
        FakeCase(id="c4", root_cause="high_value"),
    ]
    report = run_shadow_comparison(cases, _live_decide, _shadow_diverges_decide)
    assert report.total == 4
    assert report.agreements == 2
    assert report.agreement_rate == 0.5
    assert len(report.divergences) == 2
    assert {d.case_id for d in report.divergences} == {"c2", "c4"}


def test_divergence_record_captures_both_sides():
    cases = [FakeCase(id="c2", root_cause="high_value")]
    report = run_shadow_comparison(cases, _live_decide, _shadow_diverges_decide)
    d = report.divergences[0]
    assert d.live_ladder_level == "L3"
    assert d.shadow_ladder_level == "L4"
    assert d.live_amount_paise == 0
    assert d.shadow_amount_paise == 5000
    assert d.agrees is False


def test_empty_case_list_gives_vacuous_perfect_agreement():
    report = run_shadow_comparison([], _live_decide, _shadow_diverges_decide)
    assert report.total == 0
    assert report.agreement_rate == 1.0
    assert report.divergences == []


def test_shadow_module_never_imports_anything_that_touches_money():
    import app.mlops.shadow as shadow_module
    module_globals = vars(shadow_module)
    forbidden_names = {"mint_capability", "execute_with_capability", "RazorpayClient", "process_attempt"}
    assert forbidden_names.isdisjoint(module_globals.keys())

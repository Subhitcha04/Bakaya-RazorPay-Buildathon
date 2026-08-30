"""
Metrics: SLOs (page-worthy) vs diagnostics (dashboard-only), kept as
two explicitly separate registries. Two of the six SLOs page a human
at 2am; the rest wait for morning.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    PAGE = "page"
    ALERT = "alert"


@dataclass(frozen=True)
class SLODefinition:
    name: str
    description: str
    severity: Severity
    threshold_description: str


SLOS: list[SLODefinition] = [
    SLODefinition("webhook_ingest_success_rate", "Fraction of webhook deliveries ACKed successfully",
                  Severity.ALERT, ">= 99.9%"),
    SLODefinition("webhook_ingest_p99_latency_ms", "p99 latency of the webhook handler",
                  Severity.ALERT, "< 200ms"),
    SLODefinition("duplicate_financial_actions", "Count of financial actions executed more than once",
                  Severity.PAGE, "== 0"),
    SLODefinition("policy_violations", "Count of actions executed without a valid capability token",
                  Severity.PAGE, "== 0"),
    SLODefinition("workflow_completion_rate", "Fraction of opened cases that reach a terminal state",
                  Severity.ALERT, "> 98%"),
    SLODefinition("cost_per_case", "Average LLM + channel cost per case",
                  Severity.ALERT, "< configured budget"),
]

assert len(SLOS) == 6, "production-engineering addendum SS8.3 defines exactly 6 SLOs -- keep in sync"
assert sum(1 for s in SLOS if s.severity == Severity.PAGE) == 2, "exactly 2 SLOs should page a human"

DIAGNOSTIC_METRIC_NAMES: list[str] = [
    "agent_latency_p50_ms", "agent_latency_p99_ms", "tool_call_success_rate",
    "llm_error_rate", "retry_rate", "escalation_rate", "dlq_depth", "outbox_lag_seconds",
    "gate_block_rate", "cache_hit_rate", "tokens_per_workflow", "contact_rate",
    "opt_out_rate", "override_rate", "case_volume_by_surface",
]


@dataclass(frozen=True)
class SLOBreach:
    slo: SLODefinition
    observed_value: float
    message: str


def _slo(name: str) -> SLODefinition:
    return next(s for s in SLOS if s.name == name)


def check_duplicate_financial_actions(count: int) -> SLOBreach | None:
    if count != 0:
        return SLOBreach(_slo("duplicate_financial_actions"), count,
                          f"{count} duplicate financial action(s) detected -- PAGE")
    return None


def check_policy_violations(count: int) -> SLOBreach | None:
    if count != 0:
        return SLOBreach(_slo("policy_violations"), count,
                          f"{count} policy violation(s) detected -- PAGE")
    return None


def check_webhook_ingest_success_rate(success_rate: float) -> SLOBreach | None:
    if success_rate < 0.999:
        return SLOBreach(_slo("webhook_ingest_success_rate"), success_rate,
                          f"webhook ingest success rate {success_rate:.4%} below 99.9%")
    return None


def check_webhook_ingest_p99_latency(p99_ms: float) -> SLOBreach | None:
    if p99_ms >= 200:
        return SLOBreach(_slo("webhook_ingest_p99_latency_ms"), p99_ms,
                          f"webhook ingest p99 latency {p99_ms:.1f}ms >= 200ms")
    return None


def check_workflow_completion_rate(rate: float) -> SLOBreach | None:
    if rate <= 0.98:
        return SLOBreach(_slo("workflow_completion_rate"), rate,
                          f"workflow completion rate {rate:.4%} <= 98%")
    return None


def check_cost_per_case(avg_cost_paise: float, budget_paise: float) -> SLOBreach | None:
    if avg_cost_paise >= budget_paise:
        return SLOBreach(_slo("cost_per_case"), avg_cost_paise,
                          f"average cost/case {avg_cost_paise}p >= budget {budget_paise}p")
    return None

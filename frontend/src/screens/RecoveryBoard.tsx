import { useEffect, useState } from "react";
import "./RecoveryBoard.css";
import { fetchCases, fetchDashboardSummary, rupees, type CaseSummary, type DashboardSummary } from "../api";
import StatusChip from "../components/StatusChip";
import CountUp from "../components/CountUp";

interface RecoveryBoardProps {
  onSelectCase: (id: string) => void;
}

const SURFACES = ["all", "payment_failure", "checkout_abandonment", "mandate_failure", "receivable"] as const;

export default function RecoveryBoard({ onSelectCase }: RecoveryBoardProps) {
  const [surfaceFilter, setSurfaceFilter] = useState<(typeof SURFACES)[number]>("all");
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchCases(), fetchDashboardSummary()])
      .then(([c, s]) => {
        setCases(c);
        setSummary(s);
      })
      .catch(() => setError("Could not reach the API server. Is it running at http://localhost:8000?"));
  }, []);

  if (error) {
    return (
      <div className="board-error">
        <p>{error}</p>
        <p className="board-error-hint">
          Start it with: <code>uvicorn app.api.server:app --reload --port 8000</code>
        </p>
      </div>
    );
  }

  if (!cases || !summary) {
    return <div className="board-loading">Loading live data...</div>;
  }

  const filtered = surfaceFilter === "all" ? cases : cases.filter((c) => c.surface === surfaceFilter);
  const treatmentCount = summary.byArm["treatment"] ?? 0;
  const holdoutCount = summary.byArm["holdout"] ?? 0;
  const armMax = Math.max(treatmentCount, holdoutCount, 1);

  return (
    <div className="board">
      <header className="board-header">
        <div>
          <h1>Recovery board</h1>
          <p className="board-subtitle">
            Live case stream from the real control plane -- every row below is a persisted,
            gate-verified decision, not simulated data.
          </p>
        </div>
        <div className="board-seed mono">{summary.totalCases} cases</div>
      </header>

      <section className="kpi-strip">
        <div className="kpi-card kpi-card--primary">
          <span className="kpi-label">Total cases</span>
          <span className="kpi-value"><CountUp value={summary.totalCases} decimals={0} /></span>
          <span className="kpi-sub mono">
            {summary.byVerdict["ALLOW"] ?? 0} allow &middot; {summary.byVerdict["BLOCK"] ?? 0} block
          </span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Escalated to human</span>
          <span className="kpi-value"><CountUp value={summary.byVerdict["ESCALATE"] ?? 0} decimals={0} /></span>
          <span className="kpi-sub">Never autonomous, by design</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Duplicate financial actions</span>
          <span className="kpi-value kpi-value--safe">
            <CountUp value={summary.duplicateFinancialActions} decimals={0} />
          </span>
          <span className="kpi-sub">Single-use capability tokens</span>
        </div>
        <div className="kpi-card">
          <span className="kpi-label">Policy violations</span>
          <span className="kpi-value kpi-value--safe">
            <CountUp value={summary.policyViolations} decimals={0} />
          </span>
          <span className="kpi-sub">Zero by construction</span>
        </div>
      </section>

      <section className="arm-compare">
        <div className="arm-compare-header">
          <span>Case volume by experiment arm</span>
          <span className="mono">n = {treatmentCount} / {holdoutCount}</span>
        </div>
        <p className="arm-compare-note">
          Recovery-rate comparison requires Outcome data this API doesn't persist yet -- see
          scripts/run_batch.py for that measurement. This shows real case counts only.
        </p>
        <div className="arm-bars">
          <ArmBar label="Treatment" value={treatmentCount} max={armMax} colorVar="--blue-500" delay={0} />
          <ArmBar label="Holdout" value={holdoutCount} max={armMax} colorVar="--ink-400" delay={120} />
        </div>
      </section>

      <section className="filter-row">
        {SURFACES.map((s) => (
          <button
            key={s}
            className={`filter-pill ${surfaceFilter === s ? "is-active" : ""}`}
            onClick={() => setSurfaceFilter(s)}
          >
            {s === "all" ? "All surfaces" : s.replace(/_/g, " ")}
          </button>
        ))}
      </section>

      <section className="case-table">
        <div className="case-table-head">
          <span>Case</span>
          <span>Surface</span>
          <span>Root cause</span>
          <span>Ladder</span>
          <span>Arm</span>
          <span>Amount</span>
          <span>Verdict</span>
        </div>
        {filtered.slice(0, 100).map((c, i) => (
          <button
            key={c.id}
            className="case-row"
            style={{ animationDelay: `${i * 25}ms` }}
            onClick={() => onSelectCase(c.id)}
          >
            <span className="mono case-id">{c.id.slice(0, 8)}</span>
            <span className="case-surface">{c.surface.replace(/_/g, " ")}</span>
            <span>{(c.rootCause ?? "unknown").replace(/_/g, " ")}</span>
            <span className="mono">{c.ladderLevel}</span>
            <span className={`arm-tag arm-tag--${c.arm}`}>{c.arm}</span>
            <span className="mono">{rupees(c.amountPaise)}</span>
            <span>
              <StatusChip verdict={c.verdict} />
            </span>
          </button>
        ))}
      </section>
      {filtered.length > 100 && (
        <p className="board-truncated mono">showing 100 of {filtered.length} matching cases</p>
      )}
    </div>
  );
}

function ArmBar({
  label, value, max, colorVar, delay,
}: { label: string; value: number; max: number; colorVar: string; delay: number }) {
  const pct = (value / max) * 100;
  return (
    <div className="arm-bar-row">
      <span className="arm-bar-label">{label}</span>
      <div className="arm-bar-track">
        <div
          className="arm-bar-fill"
          style={{
            width: `${pct}%`,
            background: `var(${colorVar})`,
            animationDelay: `${delay}ms`,
          }}
        />
      </div>
      <span className="arm-bar-value mono">{value}</span>
    </div>
  );
}

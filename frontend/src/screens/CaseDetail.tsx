import { useEffect, useState } from "react";
import "./CaseDetail.css";
import { fetchCaseDetail, rupees, type CaseDetailResponse } from "../api";
import StatusChip from "../components/StatusChip";

interface CaseDetailProps {
  caseId: string | null;
}

export default function CaseDetail({ caseId }: CaseDetailProps) {
  const [detail, setDetail] = useState<CaseDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!caseId) return;
    setDetail(null);
    setError(null);
    fetchCaseDetail(caseId)
      .then(setDetail)
      .catch(() => setError(`Could not load case ${caseId}. It may not exist, or the API server is down.`));
  }, [caseId]);

  const toggle = (step: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(step) ? next.delete(step) : next.add(step);
      return next;
    });
  };

  if (!caseId) {
    return (
      <div className="cd-empty">
        <p>No case selected.</p>
        <p className="cd-empty-hint">Pick a case from the Recovery Board to see its evidence chain.</p>
      </div>
    );
  }

  if (error) {
    return <div className="cd-empty cd-empty--error">{error}</div>;
  }

  if (!detail) {
    return <div className="cd-empty">Loading case...</div>;
  }

  const decidedNode = detail.evidenceChain.find((n) => n.step === "decided");
  const gateResults = (decidedNode?.detail.gate_results as Record<string, boolean> | undefined) ?? null;

  return (
    <div className="case-detail">
      <header className="cd-header">
        <div>
          <div className="cd-eyebrow mono">CASE {detail.id.slice(0, 12)}</div>
          <h1>{detail.surface.replace(/_/g, " ")}</h1>
        </div>
        <StatusChip verdict={detail.verdict} />
      </header>

      <div className="cd-meta-row">
        <MetaField label="Trace ID" value={detail.traceId.slice(0, 12)} mono />
        <MetaField label="Root cause" value={(detail.rootCause ?? "unknown").replace(/_/g, " ")} />
        <MetaField label="Amount" value={rupees(detail.amountPaise)} mono />
        <MetaField label="LTV band" value={detail.ltvBand} />
        <MetaField label="Experiment arm" value={detail.arm} />
      </div>

      <div className="cd-body">
        <div className="evidence-chain">
          {detail.evidenceChain.map((node, i) => (
            <div key={node.step} className="evidence-item" style={{ animationDelay: `${i * 160}ms` }}>
              {i < detail.evidenceChain.length - 1 && (
                <span className="chain-link" style={{ animationDelay: `${i * 160 + 220}ms` }}>
                  {detail.evidenceChain[i + 1].hash && (
                    <span className="chain-link-hash mono">
                      &#8627; {detail.evidenceChain[i + 1].hash!.slice(0, 8)}
                    </span>
                  )}
                </span>
              )}

              <div className="evidence-node">
                <span className="evidence-index mono">{String(i + 1).padStart(2, "0")}</span>
              </div>

              <button className="evidence-card" onClick={() => toggle(node.step)}>
                <div className="evidence-card-top">
                  <div>
                    <div className="evidence-label">{node.label}</div>
                    <div className="evidence-summary">{node.summary}</div>
                  </div>
                  {node.hash && <div className="evidence-hash mono">{node.hash.slice(0, 8)}</div>}
                </div>
                <div className="evidence-card-foot">
                  <span className="mono">
                    {node.timestamp
                      ? new Date(node.timestamp).toLocaleTimeString("en-IN", {
                          hour: "2-digit", minute: "2-digit", second: "2-digit",
                        })
                      : "--"}
                  </span>
                  <span className="evidence-toggle">{expanded.has(node.step) ? "Hide detail" : "Show detail"}</span>
                </div>

                {expanded.has(node.step) && (
                  <div className="evidence-detail">
                    {Object.entries(node.detail)
                      .filter(([k]) => k !== "gate_results")
                      .map(([k, v]) => (
                        <div className="evidence-detail-row" key={k}>
                          <span className="evidence-detail-key mono">{k}</span>
                          <span className="evidence-detail-value mono">{String(v)}</span>
                        </div>
                      ))}
                  </div>
                )}

                {node.step === "decided" && gateResults && <GateGrid gateResults={gateResults} />}
              </button>
            </div>
          ))}
        </div>

        {detail.evidenceChain.length < 4 && detail.verdict !== "HOLDOUT" && (
          <p className="cd-scope-note">
            This case's chain stops here -- the remaining steps (Intervened / Outcome / Stopped) are
            not persisted by scripts/seed_db.py yet. See its docstring for the scope boundary.
          </p>
        )}
      </div>
    </div>
  );
}

function MetaField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="meta-field">
      <span className="meta-label">{label}</span>
      <span className={mono ? "mono meta-value" : "meta-value"}>{value}</span>
    </div>
  );
}

function GateGrid({ gateResults }: { gateResults: Record<string, boolean> }) {
  const entries = Object.entries(gateResults);
  const passedCount = entries.filter(([, passed]) => passed).length;
  return (
    <div className="gate-grid">
      <div className="gate-grid-label">{passedCount} of {entries.length} gates evaluated</div>
      <div className="gate-grid-items">
        {entries.map(([gate, passed]) => (
          <span key={gate} className={`gate-chip ${passed ? "gate-chip--pass" : "gate-chip--fail"}`}>
            {gate}
          </span>
        ))}
      </div>
    </div>
  );
}

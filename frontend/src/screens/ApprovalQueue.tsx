import { useEffect, useState } from "react";
import "./ApprovalQueue.css";
import { fetchApprovals, rupees, type ApprovalItem } from "../api";

type Action = "approve" | "reject";
const CHANNELS = ["email", "whatsapp", "sms"] as const;

function draftTemplateFor(item: ApprovalItem): string {
  const amount = rupees(item.amountPaise);
  if (item.rootCause === "fraud_flag") {
    return (
      `Hi, we've placed a temporary hold on a recent transaction of ${amount} while our team ` +
      `reviews it for your security. No action is needed from you right now -- we'll follow up ` +
      `within 24 hours. If you have questions, contact us at support@merchant.test.`
    );
  }
  return (
    `Hi, we noticed an issue with a recent transaction of ${amount} that we weren't able to ` +
    `resolve automatically. Could you let us know if this was expected, or if you'd like help ` +
    `completing it? Contact us at support@merchant.test.`
  );
}

export default function ApprovalQueue() {
  const [queue, setQueue] = useState<ApprovalItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [leaving, setLeaving] = useState<Record<string, Action>>({});
  const [composingId, setComposingId] = useState<string | null>(null);
  const [draftChannel, setDraftChannel] = useState<(typeof CHANNELS)[number]>("email");
  const [draftText, setDraftText] = useState("");

  useEffect(() => {
    fetchApprovals()
      .then(setQueue)
      .catch(() => setError("Could not reach the API server. Is it running at http://localhost:8000?"));
  }, []);

  const handleAction = (id: string, action: Action) => {
    setComposingId(null);
    setLeaving((prev) => ({ ...prev, [id]: action }));
  };

  const openCompose = (item: ApprovalItem) => {
    setComposingId((prev) => (prev === item.id ? null : item.id));
    setDraftChannel("email");
    setDraftText(draftTemplateFor(item));
  };

  const sendDraft = (id: string) => {
    handleAction(id, "approve");
  };

  const handleAnimationEnd = (id: string) => {
    if (leaving[id]) {
      setQueue((prev) => (prev ? prev.filter((item) => item.id !== id) : prev));
      setLeaving((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  };

  if (error) {
    return <div className="aq-empty">{error}</div>;
  }

  if (!queue) {
    return <div className="aq-empty">Loading approval queue...</div>;
  }

  return (
    <div className="approval-queue">
      <header className="aq-header">
        <div>
          <h1>Approval queue</h1>
          <p className="aq-subtitle">
            Every case here was routed to a human by construction -- fraud_flag or an unmapped
            cause, per ladder/levels.py. Nothing left silently.
          </p>
        </div>
        <div className="aq-count mono">{queue.length} pending</div>
      </header>

      <div className="aq-list">
        {queue.length === 0 && (
          <div className="aq-empty">Queue clear. Nothing is waiting on a human right now.</div>
        )}

        {queue.map((item, i) => (
          <div
            key={item.id}
            className={`aq-card ${leaving[item.id] ? `aq-card--leaving-${leaving[item.id]}` : ""}`}
            style={{ animationDelay: leaving[item.id] ? undefined : `${i * 70}ms` }}
            onAnimationEnd={() => handleAnimationEnd(item.id)}
          >
            <div className="aq-card-row">
              <div className="aq-card-main">
                <div className="aq-card-top">
                  <span className="mono aq-id">{item.id.slice(0, 8)}</span>
                  <span className="aq-surface">{item.surface.replace(/_/g, " ")}</span>
                  <span className={`aq-ltv aq-ltv--${item.ltvBand}`}>{item.ltvBand} value</span>
                </div>
                <p className="aq-reason">{item.reason}</p>
                <div className="aq-metrics">
                  <Metric label="Amount" value={rupees(item.amountPaise)} />
                  <Metric
                    label="Diagnosis confidence"
                    value={item.confidence !== null ? `${(item.confidence * 100).toFixed(0)}%` : "--"}
                  />
                  <Metric
                    label="Waiting since"
                    value={
                      item.waitingSince
                        ? new Date(item.waitingSince).toLocaleTimeString("en-IN", {
                            hour: "2-digit", minute: "2-digit",
                          })
                        : "--"
                    }
                  />
                </div>
              </div>

              <div className="aq-actions">
                <button className="aq-btn aq-btn--reject" onClick={() => handleAction(item.id, "reject")}>
                  Reject
                </button>
                <button className="aq-btn aq-btn--edit" onClick={() => openCompose(item)}>
                  {composingId === item.id ? "Close" : "Compose & send"}
                </button>
                <button className="aq-btn aq-btn--approve" onClick={() => handleAction(item.id, "approve")}>
                  Approve
                </button>
              </div>
            </div>

            {composingId === item.id && (
              <div className="aq-compose">
                <p className="aq-compose-note">
                  No draft exists for this case -- fraud_flag and unmapped-cause cases are never
                  given a proposed channel or copy by the Strategist (see ladder/levels.py). A
                  starting template is pre-filled below based on the diagnosed root cause -- edit
                  it before sending.
                </p>
                <div className="aq-compose-channels">
                  {CHANNELS.map((ch) => (
                    <button
                      key={ch}
                      className={`aq-channel-pill ${draftChannel === ch ? "is-active" : ""}`}
                      onClick={() => setDraftChannel(ch)}
                    >
                      {ch}
                    </button>
                  ))}
                </div>
                <textarea
                  className="aq-compose-textarea"
                  placeholder={`Write a message to send via ${draftChannel}...`}
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                  rows={4}
                />
                <div className="aq-compose-actions">
                  <button className="aq-btn aq-btn--reject" onClick={() => setComposingId(null)}>
                    Cancel
                  </button>
                  <button
                    className="aq-btn aq-btn--approve"
                    disabled={draftText.trim().length === 0}
                    onClick={() => sendDraft(item.id)}
                  >
                    Send via {draftChannel}
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="aq-metric">
      <span className="aq-metric-label">{label}</span>
      <span className="aq-metric-value mono">{value}</span>
    </div>
  );
}

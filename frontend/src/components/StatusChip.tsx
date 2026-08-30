import "./StatusChip.css";
import type { Verdict } from "../api";

const CONFIG: Record<Verdict, { label: string; className: string }> = {
  ALLOW: { label: "Allow", className: "chip-allow" },
  BLOCK: { label: "Block", className: "chip-block" },
  ESCALATE: { label: "Escalate", className: "chip-escalate" },
  HOLDOUT: { label: "Holdout", className: "chip-holdout" },
};

export default function StatusChip({ verdict }: { verdict: Verdict }) {
  const cfg = CONFIG[verdict];
  return (
    <span className={`status-chip ${cfg.className}`}>
      <span className="status-chip-dot" />
      {cfg.label}
    </span>
  );
}

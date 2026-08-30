import "./Sidebar.css";

export type Screen = "board" | "case" | "queue";

interface SidebarProps {
  active: Screen;
  onNavigate: (screen: Screen) => void;
  queueCount: number;
}

const NAV_ITEMS: { id: Screen; label: string; icon: React.ReactElement }[] = [
  {
    id: "board",
    label: "Recovery board",
    icon: (
      <svg viewBox="0 0 20 20" fill="none">
        <rect x="2.5" y="2.5" width="6" height="6" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
        <rect x="11.5" y="2.5" width="6" height="6" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
        <rect x="2.5" y="11.5" width="6" height="6" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
        <rect x="11.5" y="11.5" width="6" height="6" rx="1.2" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    id: "case",
    label: "Case detail",
    icon: (
      <svg viewBox="0 0 20 20" fill="none">
        <circle cx="6" cy="4.5" r="1.6" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="14" cy="9.5" r="1.6" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="6" cy="15" r="1.6" stroke="currentColor" strokeWidth="1.4" />
        <path d="M6 6.1 L14 8 M14 11 L6 14.2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "queue",
    label: "Approval queue",
    icon: (
      <svg viewBox="0 0 20 20" fill="none">
        <rect x="3" y="3.5" width="14" height="4" rx="1" stroke="currentColor" strokeWidth="1.4" />
        <rect x="3" y="8.5" width="14" height="4" rx="1" stroke="currentColor" strokeWidth="1.4" opacity="0.7" />
        <rect x="3" y="13.5" width="14" height="4" rx="1" stroke="currentColor" strokeWidth="1.4" opacity="0.45" />
      </svg>
    ),
  },
];

export default function Sidebar({ active, onNavigate, queueCount }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-mark">B</div>
        <div>
          <div className="sidebar-wordmark">Bakaya</div>
          <div className="sidebar-tagline">recovery control plane</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`sidebar-nav-item ${active === item.id ? "is-active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            <span className="sidebar-nav-icon">{item.icon}</span>
            <span>{item.label}</span>
            {item.id === "queue" && queueCount > 0 && (
              <span className="sidebar-nav-badge mono">{queueCount}</span>
            )}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-status">
          <span className="status-dot" />
          <span>Control plane live</span>
        </div>
        <div className="sidebar-footnote mono">policy_version v1</div>
      </div>
    </aside>
  );
}

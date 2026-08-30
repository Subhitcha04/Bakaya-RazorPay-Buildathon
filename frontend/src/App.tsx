import { useEffect, useState } from "react";
import Sidebar, { type Screen } from "./components/Sidebar";
import RecoveryBoard from "./screens/RecoveryBoard";
import CaseDetail from "./screens/CaseDetail";
import ApprovalQueue from "./screens/ApprovalQueue";
import { fetchApprovals } from "./api";

export default function App() {
  const [screen, setScreen] = useState<Screen>("board");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [queueCount, setQueueCount] = useState(0);

  useEffect(() => {
    fetchApprovals()
      .then((items) => setQueueCount(items.length))
      .catch(() => setQueueCount(0));
  }, []);

  const handleSelectCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    setScreen("case");
  };

  return (
    <div className="app-shell">
      <Sidebar active={screen} onNavigate={setScreen} queueCount={queueCount} />
      <main className="app-main">
        {screen === "board" && <RecoveryBoard onSelectCase={handleSelectCase} />}
        {screen === "case" && <CaseDetail caseId={selectedCaseId} />}
        {screen === "queue" && <ApprovalQueue />}
      </main>
    </div>
  );
}

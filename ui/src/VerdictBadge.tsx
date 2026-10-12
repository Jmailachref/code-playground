import { verdictLabel, type Verdict } from "./api";

export function VerdictBadge({ verdict }: { verdict: Verdict | null }) {
  if (!verdict) return <span className="badge badge-neutral">Failed to judge</span>;
  const tone = verdict === "accepted" ? "pass" : verdict === "wrong_answer" ? "fail" : "error";
  return <span className={`badge badge-${tone}`}>{verdictLabel[verdict]}</span>;
}

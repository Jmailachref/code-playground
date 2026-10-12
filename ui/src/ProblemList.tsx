import { useEffect, useState } from "react";
import { api, type ProblemSummary } from "./api";

export function ProblemList() {
  const [problems, setProblems] = useState<ProblemSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.problems().then(setProblems, () => setError("Could not load questions."));
  }, []);

  if (error) return <p className="error page">{error}</p>;
  if (!problems) return <p className="muted page">Loading questions…</p>;
  return (
    <div className="page">
      <h1>Questions</h1>
      {problems.length === 0 && (
        <p className="muted">No questions yet. Create one with POST /v1/problems or run the seed script.</p>
      )}
      <ul className="problem-list">
        {problems.map((p) => (
          <li key={p.id}>
            <a href={`#/problems/${p.id}`}>
              <span className="problem-title">{p.title}</span>
              <span className="muted">{p.slug}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

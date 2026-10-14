import { useEffect, useState } from "react";
import { api, levelLabel, type Language, type Level, type ProblemSummary } from "./api";
import { LevelBadge } from "./LevelBadge";
import { load, save } from "./storage";

const LEVELS: Level[] = [1, 2, 3, 4];

export function ProblemList({ languages }: { languages: Language[] }) {
  const [problems, setProblems] = useState<ProblemSummary[] | null>(null);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState(() => load("questions:language", ""));
  const [level, setLevel] = useState(() => Number(load("questions:level", "0")));

  useEffect(() => {
    api.problems().then(setProblems, () => setError("Could not load questions."));
  }, []);

  if (error) return <p className="error page">{error}</p>;
  if (!problems) return <p className="muted page">Loading questions…</p>;

  const nameOf = (id: string) => languages.find((l) => l.id === id)?.display_name ?? id;
  const shown = problems.filter((p) => (!language || p.language === language) && (!level || p.level === level));
  // Group by language, keeping the server's order (easiest first within each).
  const groups = new Map<string, ProblemSummary[]>();
  for (const p of shown) groups.set(p.language, [...(groups.get(p.language) ?? []), p]);
  const pick = (key: string, value: string, set: (v: string) => void) => (save(key, value), set(value));

  return (
    <div className="page">
      <h1>Questions</h1>
      {problems.length === 0 && (
        <p className="muted">No questions yet. Create one with POST /v1/problems or run the seed script.</p>
      )}
      {problems.length > 0 && (
        <div className="filters">
          <div className="chips" role="group" aria-label="Language">
            <button className="chip" aria-pressed={!language} onClick={() => pick("questions:language", "", setLanguage)}>
              All languages
            </button>
            {languages
              .filter((l) => problems.some((p) => p.language === l.id))
              .map((l) => (
                <button
                  key={l.id}
                  className="chip"
                  aria-pressed={language === l.id}
                  onClick={() => pick("questions:language", l.id, setLanguage)}
                >
                  {l.display_name}
                  <span className="chip-count">{problems.filter((p) => p.language === l.id).length}</span>
                </button>
              ))}
          </div>
          <select
            className="select"
            value={level}
            onChange={(e) => pick("questions:level", e.target.value, (v) => setLevel(Number(v)))}
            aria-label="Level"
          >
            <option value={0}>All levels</option>
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l} · {levelLabel[l]}
              </option>
            ))}
          </select>
        </div>
      )}
      {problems.length > 0 && shown.length === 0 && <p className="muted">No questions match these filters.</p>}
      {[...groups].map(([lang, items]) => (
        <section key={lang}>
          <h2 className="group-title">{nameOf(lang)}</h2>
          <ul className="problem-list">
            {items.map((p) => (
              <li key={p.id}>
                <a href={`#/problems/${p.id}`}>
                  <span className="problem-title">{p.title}</span>
                  <LevelBadge level={p.level} />
                </a>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

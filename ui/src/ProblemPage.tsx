import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  type Language,
  type Problem,
  type Run,
  type Submission,
  type SubmissionSummary,
} from "./api";
import { CodeEditor } from "./CodeEditor";
import { LanguagePicker } from "./LanguagePicker";
import { load, save } from "./storage";
import { VerdictBadge } from "./VerdictBadge";

interface Props {
  problemId: string;
  languages: Language[];
  userId: string;
}

type Outcome = { kind: "submission"; submission: Submission } | { kind: "test"; run: Run; caseIndex: number };

const sameOutput = (a: string, b: string) => {
  const lines = (s: string) => s.replace(/\r\n/g, "\n").split("\n").map((l) => l.trimEnd()).join("\n").trimEnd();
  return lines(a) === lines(b);
};

export function ProblemPage({ problemId, languages, userId }: Props) {
  const [problem, setProblem] = useState<Problem | null>(null);
  const [loadError, setLoadError] = useState("");
  const allowed = languages.filter((l) => !problem?.languages.length || problem.languages.includes(l.id));
  const [language, setLanguage] = useState(() => load("problem:language", "python"));
  const draftKey = (lang: string) => `draft:${problemId}:${lang}`;
  const templateFor = (lang: string) => languages.find((l) => l.id === lang)?.template ?? "";
  const [code, setCode] = useState(() => load(draftKey(language), templateFor(language)));
  const [caseIndex, setCaseIndex] = useState(0);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [busy, setBusy] = useState<"" | "test" | "submit">("");
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"result" | "history">("result");
  const [history, setHistory] = useState<SubmissionSummary[]>([]);

  useEffect(() => {
    api.problem(problemId).then(setProblem, () => setLoadError("Could not load this question."));
  }, [problemId]);

  useEffect(() => {
    if (tab === "history") api.history(problemId, userId).then(setHistory, () => setHistory([]));
  }, [tab, problemId, userId, outcome]);

  useEffect(() => {
    if (problem && allowed.length && !allowed.some((l) => l.id === language)) changeLanguage(allowed[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [problem]);

  function changeLanguage(id: string) {
    setLanguage(id);
    save("problem:language", id);
    setCode(load(draftKey(id), templateFor(id)));
  }

  function changeCode(value: string) {
    setCode(value);
    save(draftKey(language), value);
  }

  async function act(kind: "test" | "submit") {
    if (!problem) return;
    setBusy(kind);
    setError("");
    setTab("result");
    try {
      if (kind === "submit") {
        setOutcome({ kind: "submission", submission: await api.submit(problem.id, language, code, userId) });
      } else {
        const testCase = problem.scenarios[caseIndex];
        setOutcome({ kind: "test", run: await api.run(language, code, testCase.input, userId), caseIndex });
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the server");
    } finally {
      setBusy("");
    }
  }

  async function openSubmission(id: string) {
    const submission = await api.submission(id);
    setOutcome({ kind: "submission", submission });
    setLanguage(submission.language);
    setCode(submission.source_code);
    setTab("result");
  }

  if (loadError) return <p className="error page">{loadError}</p>;
  if (!problem) return <p className="muted page">Loading…</p>;

  return (
    <div className="split">
      <section className="pane statement">
        <a href="#/problems" className="back">
          ← All questions
        </a>
        <h1>{problem.title}</h1>
        <p className="muted">
          Time limit {problem.time_limit_ms} ms · Memory limit {problem.memory_limit_mb} MB
        </p>
        <div className="prose">{problem.statement}</div>
        <h2>Examples</h2>
        {problem.scenarios.map((s) => (
          <div key={s.id} className="case">
            <div className="case-name">{s.name}</div>
            <div className="case-io">
              <div>
                <div className="label">Input</div>
                <pre className="io">{s.input || " "}</pre>
              </div>
              <div>
                <div className="label">Expected output</div>
                <pre className="io">{s.expected_output || " "}</pre>
              </div>
            </div>
          </div>
        ))}
        {problem.hidden_scenarios > 0 && (
          <p className="muted">
            Plus {problem.hidden_scenarios} hidden test case{problem.hidden_scenarios > 1 ? "s" : ""} run on
            submit.
          </p>
        )}
      </section>

      <section className="pane">
        <div className="toolbar">
          <LanguagePicker languages={allowed} value={language} onChange={changeLanguage} />
          <button className="button button-secondary" onClick={() => changeCode(templateFor(language))}>
            Reset
          </button>
          <span className="spacer" />
          {problem.scenarios.length > 0 && (
            <select
              className="select"
              value={caseIndex}
              onChange={(e) => setCaseIndex(Number(e.target.value))}
              aria-label="Test case"
            >
              {problem.scenarios.map((s, i) => (
                <option key={s.id} value={i}>
                  {s.name}
                </option>
              ))}
            </select>
          )}
          <button
            className="button button-secondary"
            onClick={() => act("test")}
            disabled={!!busy || problem.scenarios.length === 0}
          >
            {busy === "test" ? "Running…" : "Run test"}
          </button>
          <button className="button" onClick={() => act("submit")} disabled={!!busy}>
            {busy === "submit" ? "Judging…" : "Submit"}
          </button>
        </div>
        <CodeEditor language={language} value={code} onChange={changeCode} />

        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === "result"} onClick={() => setTab("result")}>
            Result
          </button>
          <button role="tab" aria-selected={tab === "history"} onClick={() => setTab("history")}>
            My submissions
          </button>
        </div>
        <div className="results">
          {error && <p className="error">{error}</p>}
          {tab === "result" && !error && (
            <>
              {!outcome && (
                <p className="muted">
                  {busy ? "Working…" : "Run one test case, or submit to judge against all of them."}
                </p>
              )}
              {outcome?.kind === "test" && (
                <TestOutcome run={outcome.run} expected={problem.scenarios[outcome.caseIndex].expected_output} />
              )}
              {outcome?.kind === "submission" && <SubmissionOutcome submission={outcome.submission} />}
            </>
          )}
          {tab === "history" && <History items={history} onOpen={openSubmission} />}
        </div>
      </section>
    </div>
  );
}

function TestOutcome({ run, expected }: { run: Run; expected: string }) {
  if (run.status === "failed") return <p className="error">The platform failed to run this code. Try again.</p>;
  if (run.verdict === "compilation_error") {
    return (
      <>
        <VerdictBadge verdict="compilation_error" />
        <pre className="io io-error">{run.compile_output}</pre>
      </>
    );
  }
  const verdict = run.verdict === "accepted" && !sameOutput(run.stdout, expected) ? "wrong_answer" : run.verdict;
  return (
    <>
      <div className="meta">
        <VerdictBadge verdict={verdict} />
        <span className="muted">{run.time_ms} ms</span>
      </div>
      <Diff actual={run.stdout} expected={expected} />
      {run.stderr && <pre className="io io-error">{run.stderr}</pre>}
    </>
  );
}

function SubmissionOutcome({ submission }: { submission: Submission }) {
  if (submission.status === "failed") {
    return <p className="error">The platform failed to judge this submission. Try again.</p>;
  }
  return (
    <>
      <div className="meta">
        <VerdictBadge verdict={submission.verdict} />
        <strong>
          {submission.passed} / {submission.total} test cases passed
        </strong>
      </div>
      {submission.compile_output && <pre className="io io-error">{submission.compile_output}</pre>}
      <ul className="case-results">
        {submission.results.map((r) => (
          <li key={r.scenario}>
            <details open={r.verdict !== "accepted" && !r.hidden}>
              <summary>
                <VerdictBadge verdict={r.verdict} />
                <span>{r.scenario}</span>
                <span className="muted">{r.time_ms} ms</span>
              </summary>
              {r.hidden ? (
                <p className="muted">Hidden test case: input and output are not shown.</p>
              ) : (
                <>
                  <Diff actual={r.stdout ?? ""} expected={r.expected_output ?? ""} />
                  {r.stderr && <pre className="io io-error">{r.stderr}</pre>}
                </>
              )}
            </details>
          </li>
        ))}
      </ul>
    </>
  );
}

function Diff({ actual, expected }: { actual: string; expected: string }) {
  return (
    <div className="case-io">
      <div>
        <div className="label">Your output</div>
        <pre className="io">{actual || " "}</pre>
      </div>
      <div>
        <div className="label">Expected output</div>
        <pre className="io">{expected || " "}</pre>
      </div>
    </div>
  );
}

function History({ items, onOpen }: { items: SubmissionSummary[]; onOpen: (id: string) => void }) {
  if (!items.length) return <p className="muted">No submissions yet.</p>;
  return (
    <table className="history">
      <thead>
        <tr>
          <th>When</th>
          <th>Language</th>
          <th>Result</th>
          <th>Passed</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {items.map((s) => (
          <tr key={s.id}>
            <td>{new Date(s.created_at).toLocaleString()}</td>
            <td>{s.language}</td>
            <td>
              {s.status === "completed" ? <VerdictBadge verdict={s.verdict} /> : <span className="muted">{s.status}</span>}
            </td>
            <td>
              {s.passed} / {s.total}
            </td>
            <td>
              <button className="link" onClick={() => onOpen(s.id)}>
                Open
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

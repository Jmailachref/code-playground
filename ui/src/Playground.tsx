import { useState } from "react";
import { api, ApiError, type Language, type Run } from "./api";
import { CodeEditor } from "./CodeEditor";
import { LanguagePicker } from "./LanguagePicker";
import { load, save } from "./storage";
import { VerdictBadge } from "./VerdictBadge";

interface Props {
  languages: Language[];
  userId: string;
}

export function Playground({ languages, userId }: Props) {
  const [language, setLanguage] = useState(() => load("playground:language", "python"));
  const template = languages.find((l) => l.id === language)?.template ?? "";
  const [code, setCode] = useState(() => load(`playground:code:${language}`, template));
  const [stdin, setStdin] = useState("World\n");
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function changeLanguage(id: string) {
    const next = languages.find((l) => l.id === id);
    setLanguage(id);
    save("playground:language", id);
    setCode(load(`playground:code:${id}`, next?.template ?? ""));
    setRun(null);
  }

  function changeCode(value: string) {
    setCode(value);
    save(`playground:code:${language}`, value);
  }

  async function execute() {
    setBusy(true);
    setError("");
    setRun(null);
    try {
      setRun(await api.run(language, code, stdin, userId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the server");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="split">
      <section className="pane">
        <div className="toolbar">
          <LanguagePicker languages={languages} value={language} onChange={changeLanguage} />
          <button className="button button-secondary" onClick={() => changeCode(template)}>
            Reset to template
          </button>
          <button className="button" onClick={execute} disabled={busy}>
            {busy ? "Running…" : "Run"}
          </button>
        </div>
        <CodeEditor language={language} value={code} onChange={changeCode} />
      </section>
      <section className="pane side">
        <label className="label" htmlFor="stdin">
          Input (stdin)
        </label>
        <textarea id="stdin" className="io" value={stdin} onChange={(e) => setStdin(e.target.value)} rows={6} />
        <h2 className="label">Output</h2>
        {error && <p className="error">{error}</p>}
        {!run && !error && <p className="muted">{busy ? "Running your code…" : "Run your code to see its output."}</p>}
        {run && <RunOutput run={run} />}
      </section>
    </div>
  );
}

function RunOutput({ run }: { run: Run }) {
  if (run.status === "failed") return <p className="error">The platform failed to run this code. Try again.</p>;
  return (
    <div className="output">
      <div className="meta">
        <VerdictBadge verdict={run.verdict} />
        {run.time_ms !== null && <span className="muted">{run.time_ms} ms</span>}
        {run.memory_kb !== null && <span className="muted">{(run.memory_kb / 1024).toFixed(1)} MB</span>}
        {run.exit_code !== null && run.exit_code !== 0 && <span className="muted">exit code {run.exit_code}</span>}
      </div>
      {run.compile_output && <pre className="io io-error">{run.compile_output}</pre>}
      {run.verdict !== "compilation_error" && <pre className="io">{run.stdout || " "}</pre>}
      {run.stderr && <pre className="io io-error">{run.stderr}</pre>}
    </div>
  );
}

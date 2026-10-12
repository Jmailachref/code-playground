import { useEffect, useState } from "react";
import { api, type Language } from "./api";
import { Playground } from "./Playground";
import { ProblemList } from "./ProblemList";
import { ProblemPage } from "./ProblemPage";
import { load, save } from "./storage";

function useHashRoute(): string {
  const [hash, setHash] = useState(window.location.hash || "#/playground");
  useEffect(() => {
    const update = () => setHash(window.location.hash || "#/playground");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return hash;
}

export function App() {
  const route = useHashRoute();
  const [languages, setLanguages] = useState<Language[] | null>(null);
  const [error, setError] = useState("");
  // Until real accounts exist, a display name identifies the user's submissions.
  const [userId, setUserId] = useState(() => load("user_id", ""));

  useEffect(() => {
    api.languages().then(setLanguages, (e) => setError(e.message || "Could not reach the server"));
  }, []);

  const problemMatch = route.match(/^#\/problems\/([0-9a-f-]{36})/);
  const section = route.startsWith("#/problems") ? "problems" : "playground";

  return (
    <div className="app">
      <header className="header">
        <span className="brand">Code Playground</span>
        <nav>
          <a href="#/playground" aria-current={section === "playground" ? "page" : undefined}>
            Playground
          </a>
          <a href="#/problems" aria-current={section === "problems" ? "page" : undefined}>
            Questions
          </a>
        </nav>
        <span className="spacer" />
        {userId && (
          <button className="link" onClick={() => setUserId("")}>
            {userId} · change
          </button>
        )}
      </header>
      <main>
        {error && <p className="error page">{error}</p>}
        {!error && !languages && <p className="muted page">Loading…</p>}
        {languages && !userId && <NamePrompt onDone={(name) => (save("user_id", name), setUserId(name))} />}
        {languages && userId && section === "playground" && <Playground languages={languages} userId={userId} />}
        {languages && userId && section === "problems" && !problemMatch && <ProblemList />}
        {languages && userId && problemMatch && (
          <ProblemPage key={problemMatch[1]} problemId={problemMatch[1]} languages={languages} userId={userId} />
        )}
      </main>
    </div>
  );
}

function NamePrompt({ onDone }: { onDone: (name: string) => void }) {
  const [name, setName] = useState("");
  return (
    <form
      className="page name-prompt"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) onDone(name.trim());
      }}
    >
      <h1>Welcome</h1>
      <p className="muted">Pick a name so your submissions are saved under it.</p>
      <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoFocus />
      <button className="button" type="submit" disabled={!name.trim()}>
        Continue
      </button>
    </form>
  );
}

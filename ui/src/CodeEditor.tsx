import Editor, { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import "monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution";
import "monaco-editor/esm/vs/basic-languages/go/go.contribution";
import "monaco-editor/esm/vs/basic-languages/java/java.contribution";
import "monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution";
import "monaco-editor/esm/vs/basic-languages/python/python.contribution";
import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { useEffect, useState } from "react";

// Bundle Monaco (core + syntax highlighting for our languages only) instead
// of loading it from a CDN.
self.MonacoEnvironment = { getWorker: () => new editorWorker() };
loader.config({ monaco });

const monacoLanguage: Record<string, string> = {
  python: "python",
  javascript: "javascript",
  java: "java",
  cpp: "cpp",
  go: "go",
};

function useDarkMode(): boolean {
  const query = "(prefers-color-scheme: dark)";
  const [dark, setDark] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setDark(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return dark;
}

interface Props {
  language: string;
  value: string;
  onChange: (value: string) => void;
}

export function CodeEditor({ language, value, onChange }: Props) {
  const dark = useDarkMode();
  return (
    <div className="editor">
      <Editor
        language={monacoLanguage[language] ?? "plaintext"}
        value={value}
        onChange={(v) => onChange(v ?? "")}
        theme={dark ? "vs-dark" : "light"}
        options={{
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 4,
        }}
      />
    </div>
  );
}

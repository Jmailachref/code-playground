// Typed client for the API, called through the UI proxy (/ui-api), which
// adds the API key on the server so it never reaches the browser.

export type Verdict =
  | "compilation_error"
  | "runtime_error"
  | "time_limit_exceeded"
  | "memory_limit_exceeded"
  | "output_limit_exceeded"
  | "wrong_answer"
  | "accepted";

export type Status = "queued" | "running" | "completed" | "failed";

export interface Language {
  id: string;
  display_name: string;
  compiled: boolean;
  template: string;
}

export type Level = 1 | 2 | 3 | 4 | 5;

export interface ProblemSummary {
  id: string;
  slug: string;
  title: string;
  language: string;
  level: Level;
}

export interface TestCase {
  id: string;
  name: string;
  input: string;
  expected_output: string;
}

export interface Problem extends ProblemSummary {
  statement: string;
  time_limit_ms: number;
  memory_limit_mb: number;
  starter_code: string;
  scenarios: TestCase[];
  hidden_scenarios: number;
}

export interface Run {
  id: string;
  status: Status;
  language: string;
  verdict: Verdict | null;
  stdout: string;
  stderr: string;
  compile_output: string;
  exit_code: number | null;
  time_ms: number | null;
  memory_kb: number | null;
}

export interface CaseResult {
  scenario: string;
  verdict: Verdict;
  hidden: boolean;
  time_ms: number;
  memory_kb: number;
  exit_code: number | null;
  stdout: string | null;
  stderr: string | null;
  expected_output: string | null;
}

export interface Submission {
  id: string;
  problem_id: string;
  language: string;
  status: Status;
  verdict: Verdict | null;
  passed: number;
  total: number;
  score: number;
  max_score: number;
  compile_output: string;
  source_code: string;
  results: CaseResult[];
  created_at: string;
}

export type SubmissionSummary = Omit<Submission, "results" | "compile_output" | "source_code">;

export class ApiError extends Error {}

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/ui-api/${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(data?.error?.message ?? `Request failed (${response.status})`);
  }
  return data as T;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Poll until the job leaves the queue. */
async function waitFor<T extends { status: Status }>(path: string): Promise<T> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const job = await call<T>("GET", path);
    if (job.status === "completed" || job.status === "failed") return job;
    await sleep(400);
  }
  throw new ApiError("Timed out waiting for the result");
}

export const api = {
  languages: () => call<Language[]>("GET", "languages"),
  // The playground lists approved code questions only; QCMs are answered in RecruteHub tests.
  problems: () => call<ProblemSummary[]>("GET", "problems?kind=code&status=approved"),
  problem: (id: string) => call<Problem>("GET", `problems/${id}`),

  async run(language: string, source_code: string, stdin: string, user_id: string): Promise<Run> {
    const { id } = await call<{ id: string }>("POST", "runs", { language, source_code, stdin, user_id });
    return waitFor<Run>(`runs/${id}`);
  },

  async submit(problem_id: string, language: string, source_code: string, user_id: string): Promise<Submission> {
    const { id } = await call<{ id: string }>("POST", "submissions", { problem_id, language, source_code, user_id });
    return waitFor<Submission>(`submissions/${id}`);
  },

  submission: (id: string) => call<Submission>("GET", `submissions/${id}`),
  history: (problem_id: string, user_id: string) =>
    call<SubmissionSummary[]>(
      "GET",
      `submissions?${new URLSearchParams({ problem_id, user_id })}`,
    ),
};

export const levelLabel: Record<Level, string> = {
  1: "Beginner",
  2: "Intermediate",
  3: "Advanced",
  4: "Expert",
  5: "Master",
};

export const verdictLabel: Record<Verdict, string> = {
  accepted: "Passed",
  wrong_answer: "Wrong answer",
  compilation_error: "Compilation error",
  runtime_error: "Runtime error",
  time_limit_exceeded: "Time limit exceeded",
  memory_limit_exceeded: "Memory limit exceeded",
  output_limit_exceeded: "Output limit exceeded",
};

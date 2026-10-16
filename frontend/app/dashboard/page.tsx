"use client";

import {
  Activity,
  AlertCircle,
  ArrowRight,
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  Circle,
  Code2,
  Container,
  Cpu,
  GitBranch,
  GitCommit,
  GitPullRequest,
  Github,
  Layers3,
  Menu,
  MessageCircle,
  Mic2,
  Play,
  RefreshCw,
  Server,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Terminal,
  User,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { io, type Socket } from "socket.io-client";

type PipelineStatus = "waiting" | "active" | "done" | "error";

type BackendStatus = "connecting" | "connected" | "offline";

type LiveLogType = "info" | "success" | "error";

type LiveLog = {
  id: string;
  time: string;
  text: string;
  type: LiveLogType;
  stage?: string;
};

type SocketLogPayload = {
  message?: string;
  type?: string;
  stage?: string;
  status?: string;
  total_time?: number;
  total_time_seconds?: number;
  pr_link?: string;
  branch?: string;
  fixes?: Array<Record<string, unknown>>;
  iterations_used?: number;
  total_failures?: number;
  commits_count?: number;
  run?: Record<string, unknown>;
  environment?: Record<string, unknown>;
  knn?: Record<string, unknown>;
  diagnosis?: string | null;
  files_changed?: string[];
  verification?: Record<string, unknown>;
  rollback?: Record<string, unknown>;
  error_locations?: ErrorLocation[];
  patch_diffs?: PatchDiff[];
  language_selection?: Record<string, unknown>;
  error?: string;
};

type PipelineRun = Record<string, unknown>;

type ReviewLine = { number: number; content: string };
type ErrorLocation = {
  file_path?: string;
  line?: number;
  column?: number;
  lines?: ReviewLine[];
};
type PatchDiff = { file_path?: string; diff?: string; status?: string };
type ChatMessage = { id: string; role: "user" | "agent"; text: string };

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function records<T extends Record<string, unknown>>(value: unknown): T[] {
  return Array.isArray(value)
    ? value.filter((item): item is T => Boolean(item) && typeof item === "object")
    : [];
}

function formatElapsedTime(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return `${String(minutes).padStart(2, "0")}m ${String(remainder).padStart(2, "0")}s`;
}

const backendUrl =
  process.env.NEXT_PUBLIC_ACR_API_URL ??
  "http://localhost:8000";

const languageOptions = [
  ["auto", "Auto detect"], ["python", "python"], ["javascript", "javascript"],
  ["typescript", "typescript"], ["java", "java"], ["c", "c"], ["cpp", "cpp (C++)"],
  ["csharp", "csharp (C#)"], ["go", "go"], ["rust", "rust"], ["php", "php"], ["kotlin", "kotlin"],
] as const;

const normalizeLanguageId = (value: unknown) => {
  const normalized = String(value ?? "").trim().toLowerCase();
  const aliases: Record<string, string> = {
    "c++": "cpp", cxx: "cpp", "c#": "csharp", cs: "csharp",
    golang: "go", rs: "rust", kt: "kotlin", js: "javascript", ts: "typescript",
    "auto detect": "auto",
  };
  return aliases[normalized] ?? normalized;
};

/* -------------------------------------------------------------------------- */
/* DATA                                                                       */
/* -------------------------------------------------------------------------- */

const initialPipeline: Array<{
  label: string;
  icon: LucideIcon;
  status: PipelineStatus;
}> = [
  {
    label: "REPOSITORY",
    icon: Github,
    status: "waiting",
  },
  {
    label: "ENVIRONMENT",
    icon: Container,
    status: "waiting",
  },
  {
    label: "BUILD",
    icon: Code2,
    status: "waiting",
  },
  {
    label: "DETECT",
    icon: AlertCircle,
    status: "waiting",
  },
  {
    label: "KNN ANALYSIS",
    icon: Cpu,
    status: "waiting",
  },
  {
    label: "AI HEAL",
    icon: Sparkles,
    status: "waiting",
  },
  {
    label: "VERIFY",
    icon: ShieldCheck,
    status: "waiting",
  },
  {
    label: "PULL REQUEST",
    icon: GitPullRequest,
    status: "waiting",
  },
];

function inferPipelineStage(
  stage: string | undefined,
  message: string,
): string | undefined {
  const context =
    `${stage ?? ""} ${message}`.toLowerCase();

  if (
    /pull request|github pr|\bpr\b/.test(context)
  ) {
    return "PULL REQUEST";
  }

  if (
    /verify|validation|test passed|verified/.test(
      context,
    )
  ) {
    return "VERIFY";
  }

  if (
    /gemini|heal|repair|fix applied|healing|patch/.test(
      context,
    )
  ) {
    return "AI HEAL";
  }

  if (
    /knn|root cause|analysis|classifier|classification/.test(
      context,
    )
  ) {
    return "KNN ANALYSIS";
  }

  if (
    /detect|failure detected|error detected|failed build/.test(
      context,
    )
  ) {
    return "DETECT";
  }

  if (
    /build|compile|compilation|npm run build|pip install/.test(
      context,
    )
  ) {
    return "BUILD";
  }

  if (
    /docker|environment|container|dependency/.test(
      context,
    )
  ) {
    return "ENVIRONMENT";
  }

  if (
    /repository|repo|clone|github|git clone/.test(
      context,
    )
  ) {
    return "REPOSITORY";
  }

  return undefined;
}

const navigation = [
  {
    name: "Command Center",
    icon: Layers3,
  },
  {
    name: "Repositories",
    icon: Github,
  },
  {
    name: "Pipelines",
    icon: GitBranch,
  },
  {
    name: "Healing Engine",
    icon: Sparkles,
  },
  {
    name: "Run History",
    icon: Activity,
  },
  {
    name: "Error Analysis",
    icon: AlertCircle,
  },
  {
    name: "Pull Requests",
    icon: GitPullRequest,
  },
];

/* -------------------------------------------------------------------------- */
/* PAGE                                                                       */
/* -------------------------------------------------------------------------- */

export default function DashboardPage() {
  const [mobileOpen, setMobileOpen] =
    useState(false);

  const [activeSection, setActiveSection] =
    useState("Command Center");

  const [backendStatus, setBackendStatus] =
    useState<BackendStatus>("connecting");

  const [pipelineRunning, setPipelineRunning] =
    useState(false);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const [pipelineStages, setPipelineStages] =
    useState(() =>
      initialPipeline.map((stage) => ({
        ...stage,
      })),
    );

  const [liveLogs, setLiveLogs] =
    useState<LiveLog[]>([]);

  // A run must always be started against the repository entered by the
  // current operator. Never prefill a personal/sample GitHub repository.
  const [repoUrl, setRepoUrl] = useState("");
  const [repoBranch, setRepoBranch] = useState("main");
  const [teamName, setTeamName] = useState("ACR_AGENT");
  const [leaderName, setLeaderName] = useState("Suhas Kumar H R");
  const [languageHint, setLanguageHint] = useState("auto");
  const [runState, setRunState] = useState<PipelineRun>({});
  // Keep the general AURA conversation completely separate from the
  // pipeline-only assistant. Sharing either state makes one chat appear to
  // answer the other and leaks run context into the general assistant.
  const [auraQuestion, setAuraQuestion] = useState("");
  const [auraMessages, setAuraMessages] = useState<ChatMessage[]>([]);
  const [pipelineQuestion, setPipelineQuestion] = useState("");
  const [pipelineMessages, setPipelineMessages] = useState<ChatMessage[]>([]);
  const [assistantReady, setAssistantReady] = useState(false);
  const [auraOpen, setAuraOpen] = useState(false);
  const [auraThinking, setAuraThinking] = useState(false);

  const socketRef =
    useRef<Socket | null>(null);
  const lastStageRef = useRef<string | undefined>(undefined);
  const greetedRef = useRef(false);

  const speakWelcome = useCallback(() => {
    if (!("speechSynthesis" in window)) return;
    const voices = window.speechSynthesis.getVoices();
    const utterance = new SpeechSynthesisUtterance(
      "Welcome to A C R Agent. Your autonomous recovery command center is active.",
    );
    utterance.voice = voices.find((voice) => /en/i.test(voice.lang) && /male|daniel|david|guy/i.test(voice.name))
      ?? voices.find((voice) => /en/i.test(voice.lang))
      ?? null;
    utterance.rate = 0.9;
    utterance.pitch = 0.82;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }, []);

  useEffect(() => {
    if (greetedRef.current || !("speechSynthesis" in window)) return;
    greetedRef.current = true;
    speakWelcome();
    window.speechSynthesis.addEventListener("voiceschanged", speakWelcome);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", speakWelcome);
      window.speechSynthesis.cancel();
    };
  }, [speakWelcome]);

  useEffect(() => {
    let active = true;
    fetch(`${backendUrl}/auth/me`, { credentials: "include" })
      .then((response) => {
        if (active && !response.ok) window.location.assign("/auth");
      })
      .catch(() => {
        if (active) window.location.assign("/auth");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!pipelineRunning || runStartedAt === null) return;
    const updateElapsed = () => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - runStartedAt) / 1000)));
    };
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [pipelineRunning, runStartedAt]);

  /* ---------------------------------------------------------------------- */
  /* LIVE LOG                                                               */
  /* ---------------------------------------------------------------------- */

  const appendLog = useCallback(
    (
      text: string,
      type: LiveLogType = "info",
      stage?: string,
    ) => {
      const time =
        new Intl.DateTimeFormat("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(new Date());

      setLiveLogs((current) =>
        [
          ...current,
          {
            id: crypto.randomUUID(),
            time,
            text,
            type,
            stage,
          },
        ].slice(-50),
      );
    },
    [],
  );

  /* ---------------------------------------------------------------------- */
  /* PIPELINE UPDATE                                                        */
  /* ---------------------------------------------------------------------- */

  const updatePipelineStage = useCallback(
    (stage: string | undefined) => {
      if (!stage) return;

      const activeIndex =
        initialPipeline.findIndex(
          (item) => item.label === stage,
        );

      if (activeIndex === -1) return;

      setPipelineStages((current) =>
        current.map((item, index) => {
          if (index < activeIndex) {
            return {
              ...item,
              status: "done",
            };
          }

          if (index === activeIndex) {
            return {
              ...item,
              status: "active",
            };
          }

          return item.status === "done"
            ? item
            : {
                ...item,
                status: "waiting",
              };
        }),
      );
    },
    [],
  );

  /* ---------------------------------------------------------------------- */
  /* SOCKET.IO                                                              */
  /* ---------------------------------------------------------------------- */

  useEffect(() => {
    const socket = io(backendUrl, {
      transports: ["websocket", "polling"],
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      withCredentials: true,
    });

    socketRef.current = socket;

    socket.on("connect", () => {
      setBackendStatus("connected");
      setAssistantReady(true);

      appendLog(
        "Socket.IO stream connected to the local backend.",
        "success",
      );

    });

    socket.on("disconnect", () => {
      setBackendStatus("offline");
      setAssistantReady(false);
      setAuraThinking(false);

      appendLog(
        "Socket.IO stream disconnected from the backend.",
        "error",
      );
    });

    socket.on(
      "connect_error",
      (error) => {
        setBackendStatus("offline");

        appendLog(
          `Backend connection error: ${error.message}`,
          "error",
        );
      },
    );

    socket.on(
      "log",
      (payload: SocketLogPayload) => {
        const message =
          payload.message ??
          "Received a backend event.";

        const type: LiveLogType =
          payload.type === "error"
            ? "error"
            : payload.type === "success"
              ? "success"
              : "info";

        const stage =
          inferPipelineStage(
            payload.stage,
            message,
          );

        if (stage) lastStageRef.current = stage;

        appendLog(
          message,
          type,
          stage,
        );

        updatePipelineStage(stage);
      },
    );

    socket.on("pipeline_update", (payload: SocketLogPayload) => {
      setRunState((current) => ({
        ...current,
        ...(payload.run ?? {}),
        ...(payload.environment ? { environment: payload.environment } : {}),
        ...(payload.knn ? { knn: payload.knn } : {}),
        ...(payload.diagnosis ? { gemini_diagnosis: payload.diagnosis } : {}),
        ...(payload.files_changed ? { files_changed: payload.files_changed } : {}),
        ...(payload.verification ? { verification: payload.verification } : {}),
        ...(payload.rollback ? { rollback: payload.rollback } : {}),
        ...(payload.error_locations ? { error_locations: payload.error_locations } : {}),
        ...(payload.patch_diffs ? { patch_diffs: payload.patch_diffs } : {}),
        ...(payload.language_selection ? { language_selection: payload.language_selection } : {}),
        ...(payload.error ? { error: payload.error } : {}),
        ...(payload.stage ? { current_stage: payload.stage } : {}),
      }));
      updatePipelineStage(inferPipelineStage(payload.stage, payload.message ?? ""));
    });

    socket.on(
      "completed",
      (payload: SocketLogPayload) => {
        setPipelineRunning(false);
        const completedRun = record(payload.run ?? payload);
        const completedProject = record(completedRun.project);
        const completedStatus = String(
          completedRun.status ?? payload.status ?? "UNKNOWN",
        );
        const completedIterations = Number(
          completedRun.healing_attempt ?? completedRun.iterations_used ?? 0,
        );
        const completedFixes = records<Record<string, unknown>>(
          completedRun.fixes,
        );
        const verified = ["SUCCESS", "RECOVERED_GIT_BLOCKED"].includes(
          completedStatus,
        );
        const normalizedRun: PipelineRun = {
          ...completedRun,
          repository: completedRun.repository ?? repoUrl.trim(),
          repository_branch: completedRun.repository_branch ?? repoBranch,
          final_status: completedRun.final_status ?? completedStatus,
          healing_attempt: Number.isFinite(completedIterations)
            ? completedIterations
            : 0,
          retry_limit: completedRun.retry_limit ?? completedRun.max_retries ?? 5,
          environment: completedRun.environment ?? completedProject,
          language_selection: completedRun.language_selection ?? {
            requested: languageHint,
            detected: completedProject.language_id ?? completedProject.language,
            matches: completedProject.language_match ?? true,
          },
          last_analysis: completedRun.last_analysis ?? {
            status: verified ? "SUCCESS" : "FAILED",
            error: verified ? undefined : completedRun.error,
          },
          verification: completedRun.verification ?? {
            status: verified ? "SUCCESS" : "FAILED",
            passed: verified,
          },
          files_changed: completedRun.files_changed ?? completedFixes
            .map((fix) => String(fix.file_path ?? ""))
            .filter(Boolean),
          rollback: completedRun.rollback ?? {
            status: records<Record<string, unknown>>(
              completedRun.rollback_events,
            ).length
              ? "RECORDED"
              : "NOT_NEEDED",
          },
          git: completedRun.git ?? {
            status: completedRun.git_status ?? "SKIPPED",
            error: completedRun.git_error,
          },
        };
        const completedSeconds = Number(payload.total_time_seconds ?? record(payload.run).total_time_seconds);
        const completedMinutes = Number(payload.total_time ?? record(payload.run).total_time_minutes);
        if (Number.isFinite(completedSeconds) && completedSeconds >= 0) {
          setElapsedSeconds(Math.round(completedSeconds));
        } else if (Number.isFinite(completedMinutes) && completedMinutes >= 0) {
          setElapsedSeconds(Math.round(completedMinutes * 60));
        }
        setRunStartedAt(null);

        // The backend sends the full authoritative result in `run` (and also
        // mirrors it at the top level for compatibility with older workers).
        // Keeping the whole result here makes failure_history, compiler/test
        // output, KNN, Gemini, rollback, and verification visible to the UI.
        setRunState(normalizedRun);

        appendLog(
          payload.status
            ? `Pipeline completed with status: ${payload.status}`
            : "Pipeline completed.",
          payload.status === "SUCCESS" ? "success" : "error",
          "PULL REQUEST",
        );

        if (payload.pr_link) {
          appendLog(
            `Pull request: ${payload.pr_link}`,
            "success",
            "PULL REQUEST",
          );
        }

        if (payload.branch) {
          appendLog(
            `Recovery branch: ${payload.branch}`,
            "info",
            "PULL REQUEST",
          );
        }

        setPipelineStages((current) => {
          if (payload.status === "SUCCESS") {
            return current.map((item) => ({ ...item, status: "done" }));
          }
          if (payload.status === "RECOVERED_GIT_BLOCKED") {
            return current.map((item, index) => ({
              ...item,
              status: index < initialPipeline.length - 1
                ? "done"
                : "error",
            }));
          }
          const failedStage = lastStageRef.current;
          const failedIndex = failedStage
            ? initialPipeline.findIndex((item) => item.label === failedStage)
            : current.findIndex((item) => item.status === "active");
          return current.map((item, index) => ({
            ...item,
            status: index === failedIndex
              ? "error"
              : index < failedIndex
                ? "done"
                : item.status === "active"
                  ? "error"
                  : item.status,
          }));
        });
      },
    );

    socket.on(
      "error_fatal",
      (payload: SocketLogPayload) => {
        setPipelineRunning(false);
        const failedMinutes = Number(record(payload.run).total_time_minutes);
        if (Number.isFinite(failedMinutes) && failedMinutes >= 0) {
          setElapsedSeconds(Math.round(failedMinutes * 60));
        }
        setRunStartedAt(null);

        if (payload.run || payload.error) {
          setRunState((current) => ({
            ...current,
            ...record(payload.run),
            ...(payload.error ? { error: payload.error } : {}),
          }));
        }

        const message =
          payload.message ??
          "The backend reported a pipeline error.";

        appendLog(
          message,
          "error",
          payload.stage,
        );

        const detectedStage =
          inferPipelineStage(
            payload.stage,
            message,
          );

        if (detectedStage) {
          setPipelineStages((current) =>
            current.map((item) =>
              item.label === detectedStage
                ? {
                    ...item,
                    status: "error",
                  }
                : item,
            ),
          );
        } else {
          setPipelineStages((current) =>
            current.map((item) =>
              item.status === "active"
                ? {
                    ...item,
                    status: "error",
                  }
                : item,
            ),
          );
        }
      },
    );

    return () => {
      socket.removeAllListeners();
      socket.disconnect();
      socketRef.current = null;
    };
  }, [
    appendLog,
    updatePipelineStage,
  ]);

  /* ---------------------------------------------------------------------- */
  /* RECONNECT                                                              */
  /* ---------------------------------------------------------------------- */

  const reconnectBackend = () => {
    setBackendStatus("connecting");

    if (socketRef.current) {
      socketRef.current.connect();
    }
  };

  /* ---------------------------------------------------------------------- */
  /* RUN PIPELINE                                                           */
  /* ---------------------------------------------------------------------- */

  const runPipeline = async () => {
    if (!socketRef.current) {
      appendLog(
        "Socket connection is not initialized.",
        "error",
      );
      return;
    }

    const socket = socketRef.current;

    if (!socket.connected) {
      appendLog(
        "Backend is not connected. Please reconnect first.",
        "error",
      );

      setBackendStatus("offline");
      return;
    }

    if (pipelineRunning) {
      appendLog(
        "A pipeline is already running.",
        "info",
      );
      return;
    }

    const trimmedRepoUrl = repoUrl.trim();
    if (!trimmedRepoUrl) {
      appendLog(
        "Enter a GitHub repository URL before starting the pipeline.",
        "error",
        "REPOSITORY",
      );
      return;
    }

    try {
      const parsedRepoUrl = new URL(trimmedRepoUrl);
      const isGitHubHost = ["github.com", "www.github.com"].includes(
        parsedRepoUrl.hostname.toLowerCase(),
      );
      if (parsedRepoUrl.protocol !== "https:" || !isGitHubHost) {
        throw new Error("not a GitHub URL");
      }
    } catch {
      appendLog(
        "Enter a valid HTTPS GitHub repository URL, for example https://github.com/owner/repository.git.",
        "error",
        "REPOSITORY",
      );
      return;
    }

    try {
      setPipelineRunning(true);
      setRunStartedAt(Date.now());
      setElapsedSeconds(0);
      setLiveLogs([]);
      setPipelineMessages([]);
      lastStageRef.current = "REPOSITORY";
      setRunState({
        repository: trimmedRepoUrl,
        repository_branch: repoBranch.trim() || "main",
        current_stage: "PREP",
        final_status: "RUNNING",
        healing_attempt: 0,
        retry_limit: 5,
        language_selection: { requested: languageHint, detected: null, matches: null },
      });
      setPipelineStages(initialPipeline.map((stage) => ({ ...stage, status: "waiting" })));
      appendLog(`Starting ACR_AGENT recovery pipeline for ${trimmedRepoUrl}.`, "info", "REPOSITORY");
      socket.emit("start_agent", {
        repo_url: trimmedRepoUrl,
        repo_branch: repoBranch.trim() || "main",
        team_name: teamName.trim() || "ACR_AGENT",
        leader_name: leaderName.trim() || "Operator",
        retry_limit: 5,
        language_hint: languageHint,
      });
    } catch {
      appendLog("Pipeline request failed before it could start.", "error");
    }
    return;

    /* Legacy fixed-repository launch flow removed.

    setPipelineRunning(true);

    setLiveLogs([]);

    setPipelineStages(
      initialPipeline.map((stage) => ({
        ...stage,
        status: "waiting",
      })),
    );

    appendLog(
      "🚀 Starting ACR_AGENT autonomous recovery pipeline...",
      "info",
      "Initializing",
    );

    appendLog(
      "📂 Repository: FINAL_YEAR_PROJECT",
      "info",
      "REPOSITORY",
    );

    appendLog(
      "🤖 Autonomous healing engine initialized.",
      "info",
      "KNN ANALYSIS",
    );

    socketRef.current.emit(
      "start_agent",
      {
        repo_url: "",
        team_name: "ACR_AGENT",
        leader_name: "Suhas Kumar H R",
        retry_limit: 5,
      },
    );
    */
  };

  /* ---------------------------------------------------------------------- */
  /* BACKEND STATUS                                                         */
  /* ---------------------------------------------------------------------- */

  const backendLabel =
    backendStatus === "connected"
      ? "CONNECTED"
      : backendStatus === "connecting"
        ? "CONNECTING"
        : "OFFLINE";

  const backendDescription =
    backendStatus === "connected"
      ? "Socket.IO event stream connected"
      : backendStatus === "connecting"
        ? "Connecting to the local FastAPI backend"
        : "Start the backend on port 8000 to reconnect";

  const askAura = async () => {
    const question = auraQuestion.trim();
    if (!question || !assistantReady || auraThinking) return;

    setAuraMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: question },
    ]);
    setAuraQuestion("");
    setAuraThinking(true);

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 55_000);
    try {
      const response = await fetch(`${backendUrl}/assistant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        signal: controller.signal,
        body: JSON.stringify({ prompt: question }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(String(payload.detail ?? "AURA AI could not answer right now."));
      }
      setAuraMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "agent", text: String(payload.answer ?? "AURA returned an empty answer.") },
      ]);
    } catch (error) {
      setAuraMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "agent",
          text: error instanceof DOMException && error.name === "AbortError"
            ? "AURA AI took too long to respond. Please try again."
            : `AURA AI error: ${error instanceof Error ? error.message : "Request failed."}`,
        },
      ]);
    } finally {
      window.clearTimeout(timeoutId);
      setAuraThinking(false);
    }
  };

  const askPipeline = () => {
    const question = pipelineQuestion.trim();
    if (!question || !assistantReady) return;
    const lower = question.toLowerCase();
    const failureHistory = records<Record<string, unknown>>(runState.failure_history);
    const analysis = record(runState.last_analysis);
    const environment = record(runState.environment);
    const selection = record(runState.language_selection);
    const verification = record(runState.verification);
    const rollback = record(runState.rollback);
    const git = record(runState.git);
    const category = record(runState.knn);
    const fixes = records<Record<string, unknown>>(runState.fixes);
    const rollbackEvents = records<Record<string, unknown>>(runState.rollback_events);

    const errors = [
      ...liveLogs
        .filter((log) => log.type === "error" || /error|fail|exception|rollback/i.test(log.text))
        .map((log) => log.text),
      ...failureHistory.map((item) => String(item.error ?? item.stderr ?? item.message ?? "")),
      String(analysis.error ?? ""),
      String(analysis.stderr ?? ""),
      String(runState.error ?? ""),
    ].filter((value, index, values) => value.trim() && values.indexOf(value) === index);

    const trimText = (value: string, limit = 1800) =>
      value.length > limit ? `${value.slice(0, limit)}…` : value;
    const currentStatus = String(runState.final_status ?? runState.status ?? "WAITING");
    const currentStage = String(
      runState.current_stage ??
      lastStageRef.current ??
      (pipelineRunning ? "RUNNING" : currentStatus === "WAITING" ? "WAITING" : "COMPLETED"),
    );
    const changed = filesChanged.length
      ? filesChanged.join(", ")
      : "No verified changed files yet.";
    const diagnosis = String(
      runState.gemini_diagnosis ??
      runState.diagnosis ??
      "No Gemini diagnosis has been reported yet.",
    );
    const attempt = String(runState.healing_attempt ?? runState.iterations_used ?? 0);
    const retryLimit = String(runState.retry_limit ?? runState.max_retries ?? 5);
    const language = String(environment.language ?? selection.detected ?? "Unknown");
    const framework = String(environment.framework ?? "Unknown");
    const gitStatus = String(git.status ?? runState.git_status ?? "SKIPPED");
    const prLink = String(runState.pr_link ?? "No verified pull request has been created yet.");
    const failureText = errors.length
      ? errors.slice(-4).map((error) => trimText(error)).join("\n\n")
      : "No compiler, test, or pipeline failure has been reported by this run yet.";

    let answer: string;
    if (/^(help|what can|which questions)/.test(lower)) {
      answer = "Ask about the repository, branch, language, current stage, build/test output, failures, KNN, Gemini diagnosis, attempts, changed files, rollback, verification, GitHub PR, logs, duration, or the final result.";
    } else if (/current stage|what stage|where.*pipeline|running now/.test(lower)) {
      answer = `Current stage: ${currentStage}. Run status: ${currentStatus}.`;
    } else if (/repository|repo url|which repo|branch/.test(lower)) {
      answer = `Repository: ${String(runState.repository ?? repoUrl ?? "Not provided")}\nBranch: ${String(runState.repository_branch ?? repoBranch ?? "main")}`;
    } else if (/language|framework|package manager|build system|detected/.test(lower)) {
      answer = `Selected language: ${String(selection.requested ?? languageHint)}\nDetected language: ${language}\nFramework: ${framework}\nPackage manager: ${String(environment.package_manager ?? "Unknown")}\nBuild system: ${String(environment.build_system ?? "Unknown")}`;
    } else if (/fail|error|problem|why.*(build|test|pipeline)|root cause|compiler|test output/.test(lower)) {
      answer = `Latest authoritative failure output:\n${failureText}\n\nCommand: ${String(analysis.command ?? "Not recorded")}`;
    } else if (/knn|classif|confidence/.test(lower)) {
      answer = Object.keys(category).length
        ? `KNN category: ${String(category.category ?? "Unknown")}\nConfidence: ${String(category.confidence ?? "Not reported")}\nKNN is advisory; the compiler/test output remains authoritative.`
        : "KNN has not reported a result yet because analysis has not produced a failure classification.";
    } else if (/gemini|diagnos|repair|heal|ai fix/.test(lower)) {
      answer = `Gemini diagnosis: ${diagnosis}`;
    } else if (/file|change|patch|modified|source/.test(lower)) {
      const fixSummary = fixes
        .map((fix) => `${String(fix.file_path ?? "unknown")}: ${String(fix.description ?? fix.bug_type ?? "verified fix")}`)
        .filter(Boolean)
        .join("\n");
      answer = `Verified changed files: ${changed}${fixSummary ? `\n\nFix details:\n${fixSummary}` : ""}`;
    } else if (/retry|attempt|how many.*(left|remain)|healing/.test(lower)) {
      answer = `Healing attempt: ${attempt} of ${retryLimit}\nFailures recorded: ${String(runState.total_failures ?? failureHistory.length)}\nCurrent status: ${currentStatus}`;
    } else if (/rollback|rolled back|revert|restore/.test(lower)) {
      const latestRollback = rollbackEvents.at(-1) ?? rollback;
      answer = Object.keys(latestRollback).length
        ? `Rollback status: ${String(latestRollback.status ?? "recorded")}\nRestored files: ${String(latestRollback.restored_files ?? "Not listed")}\nReason/context: ${String(latestRollback.verification_context ?? "Not recorded")}`
        : "No rollback has been recorded for this run.";
    } else if (/verif|passed|success|result|unresolved|final status/.test(lower)) {
      answer = `Final status: ${currentStatus}\nVerification: ${String(verification.status ?? (verification.passed ? "SUCCESS" : "Not completed"))}\n${String(verification.message ?? "No verification message recorded.")}`;
    } else if (/github|pr|pull request|commit|publish|branch.*created/.test(lower)) {
      answer = `Git status: ${gitStatus}\nRecovery branch: ${String(runState.branch ?? "Not created")}\nPull request: ${prLink}${runState.git_error ? `\nGit error: ${String(runState.git_error)}` : ""}`;
    } else if (/log|trace|console|output/.test(lower)) {
      const recent = liveLogs.slice(-8).map((log) => `[${log.time}] ${log.text}`).join("\n");
      answer = recent || "No live logs have been received yet.";
    } else if (/time|duration|long|finish|complete/.test(lower)) {
      const seconds = Number(runState.total_time_seconds ?? (runState.total_time_minutes ? Number(runState.total_time_minutes) * 60 : elapsedSeconds));
      answer = `Elapsed pipeline time: ${formatElapsedTime(Number.isFinite(seconds) ? seconds : elapsedSeconds)}\nTime limit: ${String(runState.time_limit_seconds ?? 270)} seconds.`;
    } else {
      answer = `Run summary:\nStatus: ${currentStatus}\nStage: ${currentStage}\nLanguage: ${language}\nAttempt: ${attempt}/${retryLimit}\n${errors.length ? `Latest issue: ${trimText(errors.at(-1) ?? "")}` : "No failure has been recorded yet."}`;
    }
    setPipelineMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text: question },
      { id: crypto.randomUUID(), role: "agent", text: answer },
    ]);
    setPipelineQuestion("");
  };

  const environment = record(runState.environment);
  const knn = record(runState.knn);
  const verification = record(runState.verification);
  const lastAnalysis = record(runState.last_analysis);
  const filesChanged = Array.isArray(runState.files_changed)
    ? runState.files_changed.map(String)
    : [];
  const errorLocations = records<ErrorLocation>(runState.error_locations);
  const patchDiffs = records<PatchDiff>(runState.patch_diffs);
  const failureHistory = records<Record<string, unknown>>(runState.failure_history);
  const languageSelection = record(runState.language_selection);
  const hasFailure = Boolean(lastAnalysis.error ?? runState.error);
  const runRepository = typeof runState.repository === "string" && runState.repository.startsWith("https://github.com/")
    ? runState.repository
    : repoUrl.trim().startsWith("https://github.com/") ? repoUrl.trim() : null;
  const selectedRepositoryBranch = String(runState.repository_branch ?? repoBranch).trim() || "main";
  const branchPath = selectedRepositoryBranch.split("/").map(encodeURIComponent).join("/");
  const gitPublishStatus = String(runState.git_status ?? record(runState.git).status ?? "").toUpperCase();
  const githubUrl = typeof runState.pr_link === "string" && runState.pr_link.startsWith("https://github.com/")
    ? runState.pr_link
    : gitPublishStatus === "SUCCESS" && runRepository
      ? `${runRepository.replace(/\.git$/, "")}/tree/${branchPath}`
      : null;
  const sidebarGithubUrl = githubUrl
    ?? (repoUrl.trim().startsWith("https://github.com/") ? repoUrl.trim() : null);
  const failureText = String(
    lastAnalysis.error
      ?? failureHistory[0]?.error
      ?? failureHistory[0]?.stderr
      ?? runState.error
      ?? (failureHistory.length ? "Failure details are available in the run history." : "No build/test failure recorded for this run."),
  );
  const knnLabel = knn.category
    ? `${String(knn.category)} (${String(knn.confidence ?? 0)})`
    : "Not classified";
  const finalStatus = String(runState.final_status ?? "WAITING").toUpperCase();
  const resultMetric = finalStatus === "RECOVERED_GIT_BLOCKED"
    ? "VERIFIED"
    : finalStatus;
  const resultMetricChange = finalStatus === "RECOVERED_GIT_BLOCKED"
    ? "PR BLOCKED"
    : String(record(runState.git).status ?? "NOT PUBLISHED");

  /* ---------------------------------------------------------------------- */
  /* RENDER                                                                 */
  /* ---------------------------------------------------------------------- */

  return (
    <main className="acr-dashboard min-h-screen overflow-x-hidden bg-[#020407] text-white">
      {/* ------------------------------------------------------------------ */}
      {/* BACKGROUND                                                         */}
      {/* ------------------------------------------------------------------ */}

      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute left-[5%] top-[-15%] h-[650px] w-[650px] rounded-full bg-cyan-500/[0.06] blur-[160px]" />

        <div className="absolute right-[-10%] top-[15%] h-[600px] w-[600px] rounded-full bg-violet-500/[0.055] blur-[170px]" />

        <div className="absolute bottom-[-15%] left-[30%] h-[600px] w-[600px] rounded-full bg-blue-500/[0.04] blur-[170px]" />

        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.012)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.012)_1px,transparent_1px)] bg-[size:70px_70px]" />
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* MOBILE OVERLAY                                                     */}
      {/* ------------------------------------------------------------------ */}

      {mobileOpen && (
        <button
          aria-label="Close navigation"
          onClick={() =>
            setMobileOpen(false)
          }
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden"
        />
      )}

      {/* ------------------------------------------------------------------ */}
      {/* SIDEBAR                                                            */}
      {/* ------------------------------------------------------------------ */}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[270px] flex-col border-r border-white/[0.07] bg-[#05080c]/95 backdrop-blur-2xl transition-transform duration-300 lg:translate-x-0 ${
          mobileOpen
            ? "translate-x-0"
            : "-translate-x-full"
        }`}
      >
        {/* BRAND */}

        <div className="flex h-[82px] items-center justify-between border-b border-white/[0.07] px-6">
          <div className="flex items-center gap-3">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/[0.07] shadow-[0_0_30px_rgba(34,211,238,0.08)]">
              <Zap
                size={19}
                className="text-cyan-300"
                fill="currentColor"
              />

              <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,1)]" />
            </div>

            <div>
              <div className="text-sm font-bold tracking-[0.18em]">
                ACR_AGENT
              </div>

              <div className="mt-1 font-mono text-[8px] tracking-[0.25em] text-cyan-300/30">
                AUTONOMOUS RECOVERY OS
              </div>
            </div>
          </div>

          <button
            type="button"
            aria-label="Close mobile navigation"
            onClick={() =>
              setMobileOpen(false)
            }
            className="text-white/30 hover:text-white lg:hidden"
          >
            <X size={18} />
          </button>
        </div>

        {/* NAVIGATION */}

        <div className="flex-1 overflow-y-auto px-3 py-6">
          <div className="mb-3 px-3 font-mono text-[8px] uppercase tracking-[0.28em] text-white/20">
            Main System
          </div>

          <nav className="space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              const active =
                activeSection === item.name;

              return (
                <button
                  key={item.name}
                  type="button"
                  onClick={() => {
                    setActiveSection(item.name);
                    setMobileOpen(false);

                    const sectionMap: Record<
                      string,
                      string
                    > = {
                      "Command Center":
                        "command-center",

                      Repositories:
                        "repositories-section",

                      Pipelines:
                        "pipeline-section",

                      "Healing Engine":
                        "healing-section",

                      "Run History":
                        "execution-stream",

                      "Error Analysis":
                        "error-analysis-section",

                      "Pull Requests":
                        "pull-requests-section",
                    };

                    const targetId =
                      sectionMap[item.name];

                    if (targetId) {
                      requestAnimationFrame(() => {
                        document
                          .getElementById(
                            targetId,
                          )
                          ?.scrollIntoView({
                            behavior: "smooth",
                            block: "start",
                          });
                      });
                    }
                  }}
                  className={`group relative flex w-full items-center gap-3 border px-3 py-3 text-left text-xs transition-all ${
                    active
                      ? "border-cyan-400/15 bg-cyan-400/[0.065] text-white shadow-[inset_2px_0_0_rgba(103,232,249,0.8)]"
                      : "border-transparent text-white/35 hover:bg-white/[0.025] hover:text-white/80"
                  }`}
                >
                  <Icon
                    size={16}
                    className={
                      active
                        ? "text-cyan-300"
                        : "text-white/25 group-hover:text-white/60"
                    }
                  />

                  <span>{item.name}</span>

                  {active && (
                    <span className="ml-auto h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_10px_rgba(103,232,249,0.9)]" />
                  )}
                </button>
              );
            })}
          </nav>

          <div className="mt-5 px-3">
            <div className="mb-3 font-mono text-[8px] uppercase tracking-[0.28em] text-white/20">
              GitHub Review
            </div>
            {sidebarGithubUrl ? (
              <a
                href={sidebarGithubUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-3 border border-cyan-400/20 bg-cyan-400/[0.05] px-3 py-3 font-mono text-[9px] tracking-[0.12em] text-cyan-100 transition hover:border-cyan-300/55 hover:bg-cyan-400/[0.1]"
              >
                <Github size={15} />
                <span>{typeof runState.pr_link === "string" ? "VIEW PR ON GITHUB" : "VIEW SELECTED BRANCH"}</span>
                <ArrowUpRight size={13} className="ml-auto" />
              </a>
            ) : (
              <div className="border border-white/[0.08] px-3 py-3 text-[10px] leading-5 text-white/35">
                Enter a GitHub repository URL to enable review.
              </div>
            )}
            <p className="mt-2 text-[9px] leading-4 text-white/25">GitHub shows a real PR diff after a verified repair. The dashboard shows the live red/green review evidence.</p>
          </div>

          <div className="my-7 h-px bg-white/[0.05]" />

          {/* SYSTEM TELEMETRY */}

          <div className="px-3">
            <div className="mb-4 font-mono text-[8px] uppercase tracking-[0.28em] text-white/20">
              System Telemetry
            </div>

            <Telemetry
              label="BACKEND"
              value={backendLabel}
              status={backendStatus}
            />

            <Telemetry
              label="DOCKER"
              value={
                pipelineRunning
                  ? "RUNNING"
                  : runState.repository
                    ? "COMPLETE"
                    : "IDLE"
              }
            />

            <Telemetry
              label="AI ENGINE"
              value={
                runState.gemini_diagnosis
                  ? "DIAGNOSED"
                  : pipelineRunning
                    ? "ON DEMAND"
                    : "STANDBY"
              }
            />

            <Telemetry
              label="KNN MODEL"
              value={knn.category ? "CLASSIFIED" : "STANDBY"}
            />

            <Telemetry
              label="GITHUB"
              value={String(record(runState.git).status ?? "ON VERIFY")}
            />

            <Telemetry
              label="DATABASE"
              value="AUTH MANAGED"
            />
          </div>

          <div className="mt-8 px-3">
            <div className="border border-cyan-400/10 bg-cyan-400/[0.025] p-4">
              <div className="flex items-center gap-2">
                <Activity
                  size={12}
                  className="text-cyan-300"
                />

                <span className="font-mono text-[8px] tracking-[0.2em] text-cyan-300/60">
                  SYSTEM STATUS
                </span>
              </div>

              <div className="mt-4 text-lg font-semibold">
                {backendLabel}
              </div>

              <div className="mt-1 text-[10px] text-white/25">
                {backendDescription}
              </div>

              <div className="mt-4 h-1 overflow-hidden bg-white/[0.05]">
                <div
                  className={`h-full bg-gradient-to-r transition-all duration-500 ${
                    backendStatus ===
                    "offline"
                      ? "from-red-400 to-amber-400"
                      : "from-cyan-400 to-emerald-400"
                  }`}
                  style={{
                    width:
                      backendStatus ===
                      "connected"
                        ? "100%"
                        : "35%",
                  }}
                />
              </div>

              <div className="mt-2 flex justify-between font-mono text-[7px] text-white/20">
                <span>
                  EVENT STREAM
                </span>

                <span>
                  {backendStatus ===
                  "connected"
                    ? "READY"
                    : "PENDING"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* USER + LOGOUT */}

        <div className="border-t border-white/[0.07] p-4">
          <div className="border border-white/[0.06] bg-white/[0.02] p-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-cyan-400/15 bg-cyan-400/[0.06]">
                <User
                  size={14}
                  className="text-cyan-300"
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium">
                  Authenticated User
                </div>

                <div className="mt-1 font-mono text-[8px] text-emerald-300/50">
                  SESSION ACTIVE
                </div>
              </div>

              <Settings
                size={14}
                className="text-white/20"
              />
            </div>

            <button
              type="button"
              onClick={async () => {
                await fetch(`${backendUrl}/auth/logout`, {
                  method: "POST",
                  credentials: "include",
                });
                window.location.assign("/auth");
              }}
              className="mt-3 flex w-full items-center justify-center gap-2 border border-red-400/10 bg-red-400/[0.03] px-3 py-2 font-mono text-[8px] tracking-[0.15em] text-red-300/60 transition hover:border-red-400/20 hover:bg-red-400/[0.07] hover:text-red-300"
            >
              <X size={12} />
              SIGN OUT
            </button>

            <button
              type="button"
              onClick={() => window.location.assign(`${backendUrl}/auth/google/start`)}
              className="mt-2 flex w-full items-center justify-center gap-2 border border-cyan-400/15 bg-cyan-400/[0.04] px-3 py-2 font-mono text-[8px] tracking-[0.15em] text-cyan-200/80 transition hover:border-cyan-400/35 hover:bg-cyan-400/[0.09] hover:text-cyan-100"
            >
              <span className="text-xs leading-none">G</span>
              LINK GOOGLE ACCOUNT
            </button>
          </div>
        </div>
      </aside>

      {/* ------------------------------------------------------------------ */}
      {/* MAIN                                                               */}
      {/* ------------------------------------------------------------------ */}

      <div className="lg:pl-[270px]">
        {/* HEADER */}

        <header className="sticky top-0 z-30 border-b border-white/[0.07] bg-[#030507]/80 backdrop-blur-xl">
          <div className="relative flex h-[82px] items-center justify-between px-5 sm:px-8 lg:px-10">
            <div className="pointer-events-none absolute inset-x-20 text-center">
              <span className="acr-welcome-crest inline-block whitespace-nowrap text-xl font-black tracking-[0.12em] sm:text-2xl">
                WELCOME TO ACR AGENT
              </span>
            </div>
            <div className="flex items-center gap-4">
              <button
                type="button"
                aria-label="Open navigation"
                onClick={() =>
                  setMobileOpen(true)
                }
                className="border border-white/[0.08] bg-white/[0.025] p-2 text-white/50 lg:hidden"
              >
                <Menu size={18} />
              </button>

              <div>
                <div className="font-mono text-[8px] uppercase tracking-[0.3em] text-cyan-300/30">
                  Autonomous Recovery Environment
                </div>

                <div className="mt-1 text-sm font-medium">
                  Command Center
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <div
                className={`hidden items-center gap-2 border px-3 py-2 sm:flex ${
                  backendStatus ===
                  "connected"
                    ? "border-emerald-400/10 bg-emerald-400/[0.04]"
                    : backendStatus ===
                        "connecting"
                      ? "border-amber-400/10 bg-amber-400/[0.04]"
                      : "border-red-400/10 bg-red-400/[0.04]"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full shadow-[0_0_9px_currentColor] ${
                    backendStatus ===
                    "connected"
                      ? "animate-pulse bg-emerald-400 text-emerald-400"
                      : backendStatus ===
                          "connecting"
                        ? "animate-pulse bg-amber-400 text-amber-400"
                        : "bg-red-400 text-red-400"
                  }`}
                />

                <span
                  className={`font-mono text-[8px] tracking-[0.15em] ${
                    backendStatus ===
                    "connected"
                      ? "text-emerald-300"
                      : backendStatus ===
                          "connecting"
                        ? "text-amber-300"
                        : "text-red-300"
                  }`}
                >
                  BACKEND{" "}
                  {backendLabel}
                </span>
              </div>

              <button
                type="button"
                onClick={
                  reconnectBackend
                }
                title="Reconnect to the local backend"
                className="border border-white/[0.08] bg-white/[0.025] p-2 text-white/40 transition hover:border-cyan-400/20 hover:text-cyan-300"
              >
                <RefreshCw size={16} />
              </button>

              <button
                type="button"
                onClick={() => setAuraOpen((open) => !open)}
                aria-expanded={auraOpen}
                aria-label="Open AURA AI chat"
                className="group flex items-center gap-2 border border-violet-300/20 bg-violet-400/[0.05] p-1.5 pr-2 text-left transition hover:border-violet-300/50 hover:bg-violet-400/[0.1]"
              >
                <span className="relative block h-8 w-8 overflow-hidden rounded-full border border-violet-200/35 bg-violet-300/10">
                  <img src="/images/aura-ai.png" alt="" className="h-full w-full object-cover object-top" />
                  <span className="absolute bottom-0 right-0 h-2 w-2 rounded-full border border-[#05070b] bg-emerald-400" />
                </span>
                <span className="hidden leading-tight sm:block">
                  <span className="block font-mono text-[9px] font-bold tracking-[0.18em] text-violet-100">AURA AI</span>
                  <span className="block text-[7px] tracking-[0.14em] text-violet-200/45">GENERAL AI</span>
                </span>
              </button>
            </div>
          </div>

          {auraOpen && (
            <section className="absolute right-5 top-[calc(100%+12px)] z-50 w-[min(420px,calc(100vw-2.5rem))] border border-violet-300/25 bg-[#080a12]/95 shadow-[0_24px_70px_rgba(0,0,0,0.55)] backdrop-blur-2xl sm:right-8 lg:right-10">
              <div className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="relative h-10 w-10 overflow-hidden rounded-full border border-violet-200/40 bg-violet-300/10">
                    <img src="/images/aura-ai.png" alt="AURA AI avatar" className="h-full w-full object-cover object-top" />
                    <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-[#080a12] bg-emerald-400" />
                  </div>
                  <div>
                    <p className="font-mono text-[10px] font-bold tracking-[0.2em] text-violet-100">AURA AI</p>
                    <p className="mt-0.5 text-[10px] text-white/40">General AI assistant</p>
                  </div>
                </div>
                <button type="button" onClick={() => setAuraOpen(false)} className="p-1 text-white/45 transition hover:text-white" aria-label="Close AURA AI chat">
                  <X size={16} />
                </button>
              </div>
              <div className="max-h-72 min-h-40 space-y-3 overflow-y-auto p-4">
                {auraMessages.length === 0 ? (
                  <div className="rounded border border-violet-300/12 bg-violet-400/[0.04] p-3 text-xs leading-5 text-white/55">
                    Ask AURA general questions about coding, technology, writing, ideas, or everyday topics. For this run&apos;s status, use the separate Pipeline Assistant below.
                  </div>
                ) : auraMessages.slice(-8).map((message) => (
                  <div key={`aura-${message.id}`} className={message.role === "user" ? "text-right" : "text-left"}>
                    <span className={`inline-block max-w-[92%] px-3 py-2 text-xs leading-5 ${message.role === "user" ? "bg-violet-400/15 text-violet-50" : "bg-white/[0.06] text-white/75"}`}>
                      {message.text}
                    </span>
                  </div>
                ))}
                {auraThinking && <p className="font-mono text-[9px] tracking-[0.15em] text-violet-200/60">AURA IS THINKING…</p>}
              </div>
              <div className="border-t border-white/[0.08] p-3">
                <div className="flex gap-2">
                  <input
                    value={auraQuestion}
                    onChange={(event) => setAuraQuestion(event.target.value)}
                    onKeyDown={(event) => { if (event.key === "Enter") void askAura(); }}
                    disabled={!assistantReady || auraThinking}
                    maxLength={1500}
                    placeholder="Ask AURA anything…"
                    className="h-10 min-w-0 flex-1 border border-white/[0.1] bg-black/25 px-3 text-xs text-white outline-none placeholder:text-white/25 focus:border-violet-300/50 disabled:opacity-50"
                  />
                  <button type="button" onClick={() => void askAura()} disabled={!assistantReady || !auraQuestion.trim() || auraThinking} className="flex h-10 items-center justify-center border border-violet-300/30 bg-violet-400/[0.1] px-3 text-violet-100 transition hover:bg-violet-400/[0.18] disabled:opacity-40" aria-label="Ask AURA AI">
                    <Send size={15} />
                  </button>
                </div>
                <p className="mt-2 font-mono text-[8px] tracking-[0.1em] text-white/30">LIVE RUN ANSWERS STAY LOCAL · GENERAL QUESTIONS USE AURA</p>
              </div>
            </section>
          )}
        </header>

        {/* CONTENT */}

        <div className="mx-auto max-w-[1750px] px-5 py-7 sm:px-8 lg:px-10">
          {/* ---------------------------------------------------------------- */}
          {/* HERO                                                             */}
          {/* ---------------------------------------------------------------- */}

          <section
            id="command-center"
            className="relative overflow-hidden border border-white/[0.08] bg-[#060a0f]"
          >
            <div className="absolute inset-0">
              <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:40px_40px]" />
            </div>

            <div className="absolute right-0 top-0 h-full w-[60%] bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.1),transparent_58%)]" />

            <div className="absolute left-[-100px] top-[-100px] h-[300px] w-[300px] rounded-full border border-cyan-400/[0.04]" />

            <div className="relative grid lg:grid-cols-[1.05fr_0.95fr]">
              {/* HERO TEXT */}

              <div className="flex flex-col justify-center px-6 py-14 sm:px-10 lg:px-14 lg:py-20">
                <div className="mb-6 flex items-center gap-3">
                  <span className="h-px w-10 bg-cyan-400/50" />

                  <span className="font-mono text-[9px] tracking-[0.3em] text-cyan-300/70">
                    AI / DEVOPS /
                    AUTONOMOUS
                  </span>
                </div>

                <div className="mb-5 inline-flex w-fit items-center gap-2 border border-cyan-400/10 bg-cyan-400/[0.03] px-3 py-1.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      backendStatus ===
                      "connected"
                        ? "animate-pulse bg-cyan-300"
                        : backendStatus ===
                            "connecting"
                          ? "animate-pulse bg-amber-300"
                          : "bg-red-300"
                    }`}
                  />

                  <span className="font-mono text-[8px] tracking-[0.2em] text-cyan-300/60">
                    BACKEND{" "}
                    {backendLabel}
                  </span>
                </div>

                <div className="mb-5 flex w-fit items-center gap-2 border border-emerald-400/20 bg-emerald-400/[0.04] px-3 py-1.5 font-mono text-[9px] tracking-[0.22em] text-emerald-300 animate-[pulse_1.6s_ease-in-out_infinite]">
                  <Mic2 size={12} /> ACR CORE // ACTIVE
                </div>

                <h1 className="acr-title-drift max-w-3xl text-5xl font-bold leading-[0.93] tracking-[-0.055em] sm:text-6xl lg:text-7xl">
                  Code fails.
                  <br />

                  <span className="bg-gradient-to-r from-cyan-200 via-white to-violet-300 bg-clip-text text-transparent">
                    ACR_AGENT
                  </span>

                  <br />

                  <span className="text-white/30">
                    recovers.
                  </span>
                </h1>

                <p className="mt-7 max-w-xl text-sm leading-7 text-white/40">
                  Autonomous CI/CD failure
                  recovery powered by Docker
                  isolation, KNN root-cause
                  classification and
                  AI-generated repair
                  workflows.
                </p>

                <div className="mt-7 grid max-w-3xl gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <label className="sm:col-span-2 xl:col-span-4">
                    <span className="mb-1.5 block font-mono text-[8px] tracking-[0.16em] text-white/35">
                      GITHUB REPOSITORY
                    </span>
                    <input
                      value={repoUrl}
                      onChange={(event) => setRepoUrl(event.target.value)}
                      disabled={pipelineRunning}
                      placeholder="https://github.com/owner/repository.git"
                      className="h-10 w-full border border-white/[0.1] bg-black/25 px-3 font-mono text-xs text-white outline-none placeholder:text-white/20 focus:border-cyan-400/40 disabled:opacity-50"
                    />
                  </label>
                  <label>
                    <span className="mb-1.5 block font-mono text-[8px] tracking-[0.16em] text-white/35">GITHUB BRANCH</span>
                    <input value={repoBranch} onChange={(event) => setRepoBranch(event.target.value)} disabled={pipelineRunning} placeholder="main" className="h-10 w-full border border-white/[0.1] bg-black/25 px-3 font-mono text-xs text-white outline-none placeholder:text-white/20 focus:border-cyan-400/40 disabled:opacity-50" />
                  </label>
                  <label>
                    <span className="mb-1.5 block font-mono text-[8px] tracking-[0.16em] text-white/35">TEAM</span>
                    <input value={teamName} onChange={(event) => setTeamName(event.target.value)} disabled={pipelineRunning} className="h-10 w-full border border-white/[0.1] bg-black/25 px-3 text-xs text-white outline-none focus:border-cyan-400/40 disabled:opacity-50" />
                  </label>
                  <label>
                    <span className="mb-1.5 block font-mono text-[8px] tracking-[0.16em] text-white/35">OPERATOR</span>
                    <input value={leaderName} onChange={(event) => setLeaderName(event.target.value)} disabled={pipelineRunning} className="h-10 w-full border border-white/[0.1] bg-black/25 px-3 text-xs text-white outline-none focus:border-cyan-400/40 disabled:opacity-50" />
                  </label>
                  <label>
                    <span className="mb-1.5 block font-mono text-[8px] tracking-[0.16em] text-white/35">LANGUAGE TARGET</span>
                    <select
                      value={languageHint}
                      onChange={(event) => setLanguageHint(event.target.value)}
                      disabled={pipelineRunning}
                      className="h-10 w-full border border-white/[0.1] bg-black/25 px-3 text-xs text-white outline-none focus:border-cyan-400/40 disabled:opacity-50"
                    >
                      {languageOptions.map(([value, label]) => <option key={value} value={value} className="bg-[#070b10]">{label}</option>)}
                    </select>
                    <span className="mt-1.5 block text-[9px] leading-4 text-white/30">Use Auto detect unless this target matches the repository&apos;s detected build language.</span>
                  </label>
                </div>

                {languageSelection.matches === false && (
                  <div className="mt-4 border border-amber-300/25 bg-amber-300/[0.06] px-4 py-3 text-xs leading-5 text-amber-100">
                    Target mismatch: this repository was detected as <strong>{normalizeLanguageId(languageSelection.detected)}</strong>, but <strong>{normalizeLanguageId(languageSelection.requested)}</strong> was selected. Choose <strong>Auto detect</strong> or the matching GitHub folder name, then run again.
                  </div>
                )}

                {/* PIPELINE CONTROLS */}

                <div className="mt-8 flex flex-wrap gap-3">
                  <button
                    type="button"
                    disabled={
                      backendStatus !==
                        "connected" ||
                      pipelineRunning
                    }
                    onClick={
                      runPipeline
                    }
                    title={
                      backendStatus !==
                      "connected"
                        ? "Connect to the backend first"
                        : pipelineRunning
                          ? "Pipeline is already running"
                          : "Start ACR_AGENT recovery pipeline"
                    }
                    className={`group flex items-center gap-2 px-5 py-3 text-xs font-bold transition ${
                      backendStatus ===
                        "connected" &&
                      !pipelineRunning
                        ? "cursor-pointer bg-cyan-300 text-black hover:bg-cyan-200"
                        : "cursor-not-allowed bg-white/20 text-white/30"
                    }`}
                  >
                    {pipelineRunning ? (
                      <RefreshCw
                        size={14}
                        className="animate-spin"
                      />
                    ) : (
                      <Play
                        size={14}
                        fill="currentColor"
                      />
                    )}

                    {pipelineRunning
                      ? "PIPELINE RUNNING"
                      : backendStatus ===
                          "connected"
                        ? "RUN PIPELINE"
                        : "PIPELINE CONTROL DISABLED"}

                    {!pipelineRunning && (
                      <ArrowUpRight
                        size={14}
                        className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                      />
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() =>
                      document
                        .getElementById(
                          "execution-stream",
                        )
                        ?.scrollIntoView({
                          behavior:
                            "smooth",
                        })
                    }
                    className="flex items-center gap-2 border border-white/10 bg-white/[0.025] px-5 py-3 text-xs font-semibold text-white/60 transition hover:border-cyan-400/20 hover:text-white"
                  >
                    <Activity size={14} />
                    VIEW ACTIVITY
                  </button>
                </div>

                <div className="mt-9 flex flex-wrap gap-7">
                  <MiniStat
                    label="RECOVERY RATE"
                    value="91.8%"
                  />

                  <MiniStat
                    label="AVG. REPAIR"
                    value="38s"
                  />

                  <MiniStat
                    label="AI CONFIDENCE"
                    value="94.2%"
                  />
                </div>
              </div>

              {/* AI CORE */}

              <div className="relative flex min-h-[480px] items-center justify-center overflow-hidden">
                <div className="absolute h-[390px] w-[390px] rounded-full border border-cyan-400/[0.05]" />

                <div className="absolute h-[320px] w-[320px] rounded-full border border-cyan-400/[0.07]" />

                <div className="absolute h-[245px] w-[245px] rounded-full border border-violet-400/[0.1]" />

                <div className="absolute h-[340px] w-[340px] animate-[spin_18s_linear_infinite] rounded-full border border-dashed border-cyan-400/10" />

                <div className="absolute h-[280px] w-[280px] animate-[spin_25s_linear_infinite_reverse] rounded-full border border-dashed border-violet-400/10" />

                <div className="relative z-10 flex h-36 w-36 items-center justify-center rounded-[2rem] border border-cyan-300/20 bg-cyan-300/[0.055] shadow-[0_0_120px_rgba(34,211,238,0.16)]">
                  <div className="absolute inset-3 rounded-[1.5rem] border border-cyan-300/10" />

                  <div className="absolute inset-7 animate-pulse rounded-full bg-cyan-400/[0.05]" />

                  <Bot
                    size={50}
                    className="relative text-cyan-300"
                  />

                  <span className="absolute -bottom-8 whitespace-nowrap font-mono text-[8px] tracking-[0.25em] text-cyan-300/60">
                    ACR CORE // ACTIVE
                  </span>
                </div>

                <CoreNode
                  icon={AlertCircle}
                  label="DETECT"
                  position="left-[5%] top-[20%]"
                />

                <CoreNode
                  icon={Cpu}
                  label="KNN"
                  position="right-[7%] top-[18%]"
                />

                <CoreNode
                  icon={Sparkles}
                  label="GEMINI"
                  position="left-[9%] bottom-[18%]"
                />

                <CoreNode
                  icon={ShieldCheck}
                  label="VERIFY"
                  position="right-[8%] bottom-[18%]"
                />

                <CoreNode
                  icon={Container}
                  label="DOCKER"
                  position="left-[39%] top-[5%]"
                />
              </div>
            </div>
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* METRICS                                                          */}
          {/* ---------------------------------------------------------------- */}

          <section className="mt-5 grid grid-cols-2 border border-white/[0.07] bg-white/[0.015] sm:grid-cols-3 lg:grid-cols-6">
            <Metric
              label="REPOSITORY"
              value={runState.repository ? "SET" : "NONE"}
              change={runState.repository ? "CURRENT" : "WAITING"}
            />

            <Metric
              label="LANGUAGE"
              value={String(environment.language ?? "—")}
              change={String(environment.framework ?? "NOT DETECTED")}
            />

            <Metric
              label="FAILURES"
              value={String(runState.total_failures ?? 0)}
              change={lastAnalysis.error ? "DETECTED" : "NONE"}
            />

            <Metric
              label="ATTEMPT"
              value={String(runState.healing_attempt ?? 0)}
              change={`OF ${String(runState.retry_limit ?? 5)}`}
            />

            <Metric
              label="ACTIVE RUNS"
              value={
                pipelineRunning
                  ? "01"
                  : "00"
              }
              change="LIVE"
            />

            <Metric
              label="RESULT"
              value={resultMetric}
              change={resultMetricChange}
            />
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* TEAM / REPOSITORIES                                              */}
          {/* ---------------------------------------------------------------- */}

          <section
            id="repositories-section"
            className="mt-14 scroll-mt-24"
          >
            <SectionTitle
              eyebrow="PROJECT TEAM"
              title="Engineering the recovery system"
              description="The people responsible for designing, developing and validating ACR_AGENT."
            />

            <div className="mt-5 grid gap-px border border-white/[0.07] bg-white/[0.07] lg:grid-cols-[1.2fr_0.8fr]">
              <div className="bg-[#070b10] p-6 sm:p-8">
                <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
                  <div className="relative flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-full border border-cyan-300/20 bg-cyan-300/[0.05] shadow-[0_0_50px_rgba(34,211,238,0.06)]">
                    <img
                      src="/images/team-leader.png"
                      alt="ACR_AGENT team leader"
                      className="h-full w-full object-cover object-[58%_center]"
                    />

                    <span className="absolute bottom-2 right-2 h-3 w-3 rounded-full border-2 border-[#070b10] bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.8)]" />
                  </div>

                  <div>
                    <div className="font-mono text-[8px] tracking-[0.3em] text-cyan-300/60">
                      TEAM LEADER
                    </div>

                    <h3 className="mt-3 text-2xl font-semibold">
                      Suhas Kumar H R
                    </h3>

                    <p className="mt-2 text-sm text-white/35">
                      Team Leader /
                      Developer
                    </p>

                    <div className="mt-5 flex flex-wrap gap-2">
                      <a href="mailto:hsuhas42@gmail.com" className="border border-white/[0.07] px-3 py-1.5 font-mono text-[8px] text-white/55 transition hover:border-cyan-400/30 hover:text-cyan-200">
                        hsuhas42@gmail.com
                      </a>

                      <a href="https://github.com/SuhasKumarHR" target="_blank" rel="noreferrer" className="border border-white/[0.07] px-3 py-1.5 font-mono text-[8px] text-white/55 transition hover:border-cyan-400/30 hover:text-cyan-200">
                        github.com/SuhasKumarHR
                      </a>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 bg-[#05080c]">
                <TeamMember label="TEAM MEMBER 01" name="Niranjan C L" />
                <TeamMember label="TEAM MEMBER 02" name="ShivaKumar S B" />
                <TeamMember label="TEAM MEMBER 03" name="Vinay C J" />
              </div>
            </div>
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* LIVE PIPELINE                                                    */}
          {/* ---------------------------------------------------------------- */}

          <section
            id="pipeline-section"
            className="mt-14 scroll-mt-24"
          >
            <SectionTitle
              eyebrow="LIVE RECOVERY PIPELINE"
              title="Failure → analysis → healing → verification"
              description="Monitor the autonomous recovery lifecycle in real time."
            />

            <div className="relative mt-5 overflow-x-auto border border-white/[0.07] bg-[#05080c] p-6 sm:p-8">
              <div className="flex min-w-[950px] items-start">
                {pipelineStages.map(
                  (item, index) => {
                    const Icon =
                      item.icon;

                    return (
                      <div
                        key={item.label}
                        className="flex flex-1 items-start"
                      >
                        <div className="flex min-w-[105px] flex-col items-center text-center">
                          <div
                            className={`relative flex h-12 w-12 items-center justify-center border transition ${
                              item.status ===
                              "done"
                                ? "border-emerald-400/20 bg-emerald-400/[0.05]"
                                : item.status ===
                                    "active"
                                  ? "border-cyan-400/30 bg-cyan-400/[0.07] shadow-[0_0_35px_rgba(34,211,238,0.12)]"
                                  : item.status ===
                                      "error"
                                    ? "border-red-400/30 bg-red-400/[0.07]"
                                    : "border-white/[0.08] bg-white/[0.02]"
                            }`}
                          >
                            <Icon
                              size={17}
                              className={
                                item.status ===
                                "done"
                                  ? "text-emerald-300"
                                  : item.status ===
                                      "active"
                                    ? "text-cyan-300"
                                    : item.status ===
                                        "error"
                                      ? "text-red-300"
                                      : "text-white/20"
                              }
                            />

                            {item.status ===
                              "active" && (
                              <span className="absolute -right-1 -top-1 h-2 w-2 animate-pulse rounded-full bg-cyan-300 shadow-[0_0_10px_rgba(103,232,249,1)]" />
                            )}

                            {item.status ===
                              "error" && (
                              <span className="absolute -right-1 -top-1 h-2 w-2 animate-pulse rounded-full bg-red-400 shadow-[0_0_10px_rgba(248,113,113,1)]" />
                            )}
                          </div>

                          <div className="mt-3 font-mono text-[8px] tracking-wider text-white/45">
                            {item.label}
                          </div>

                          <div
                            className={`mt-1 font-mono text-[7px] uppercase ${
                              item.status ===
                              "done"
                                ? "text-emerald-400"
                                : item.status ===
                                    "active"
                                  ? "text-cyan-300"
                                  : item.status ===
                                      "error"
                                    ? "text-red-300"
                                    : "text-white/20"
                            }`}
                          >
                            {item.status}
                          </div>
                        </div>

                        {index <
                          pipelineStages.length -
                            1 && (
                          <div className="mt-6 h-px flex-1 bg-gradient-to-r from-cyan-400/20 via-cyan-400/10 to-white/[0.05]" />
                        )}
                      </div>
                    );
                  },
                )}
              </div>
            </div>
          </section>

          <section className="mt-5 grid gap-px border border-white/[0.07] bg-white/[0.07] sm:grid-cols-2 xl:grid-cols-4">
            <DataCell label="REPOSITORY" value={String(runState.repository ?? "Not started")} />
            <DataCell label="REPOSITORY BRANCH" value={String(runState.repository_branch ?? repoBranch)} />
            <DataCell label="LANGUAGE / FRAMEWORK" value={`${String(environment.language ?? "Unknown")} / ${String(environment.framework ?? "Unknown")}`} />
            <DataCell label="LANGUAGE SELECTION" value={`${String(languageSelection.requested ?? languageHint)} / ${String(languageSelection.detected ?? "Awaiting detection")}`} />
            <DataCell label="CURRENT STAGE" value={String(runState.current_stage ?? "Waiting")} />
            <DataCell label="FINAL STATUS" value={String(runState.final_status ?? "Waiting")} />
            <DataCell label="BUILD / TEST" value={String(verification.status ?? (lastAnalysis.status ?? "Not run"))} />
            <DataCell label="HEALING ATTEMPT" value={`${String(runState.healing_attempt ?? 0)} / ${String(runState.retry_limit ?? 5)}`} />
            <DataCell label="FILES CHANGED" value={filesChanged.length ? filesChanged.join(", ") : "None"} />
            <DataCell label="ROLLBACK" value={String(record(runState.rollback).status ?? "Not needed")} />
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* ANALYSIS / HEALING                                               */}
          {/* ---------------------------------------------------------------- */}

          <section
            id="healing-section"
            className="mt-5 scroll-mt-24 grid gap-px border border-white/[0.07] bg-white/[0.07] xl:grid-cols-2"
          >
            <div
              id="error-analysis-section"
              className="scroll-mt-24 bg-[#070b10] p-6 sm:p-8"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-mono text-[8px] tracking-[0.25em] text-red-300/60">
                    {hasFailure ? "ERROR SIGNAL" : "BUILD SIGNAL"}
                  </div>

                  <h2 className="mt-2 text-xl font-semibold">
                    {hasFailure ? "Root cause detected" : "No failure detected"}
                  </h2>
                </div>

                <div className={`flex items-center gap-2 border px-3 py-1.5 ${hasFailure ? "border-red-400/10 bg-red-400/[0.04]" : "border-emerald-400/15 bg-emerald-400/[0.04]"}`}>
                  <span className={`h-1.5 w-1.5 animate-pulse rounded-full ${hasFailure ? "bg-red-400" : "bg-emerald-400"}`} />

                  <span className={`font-mono text-[8px] ${hasFailure ? "text-red-300" : "text-emerald-300"}`}>
                    {hasFailure ? "FAILURE" : "PASSED"}
                  </span>
                </div>
              </div>

              <div className={`mt-6 border p-5 ${hasFailure ? "border-red-400/10 bg-red-400/[0.025]" : "border-emerald-400/10 bg-emerald-400/[0.025]"}`}>
                <div className="font-mono text-[9px] text-white/25">
                  {String(lastAnalysis.project_path ?? environment.project_path ?? "Awaiting pipeline data")}
                </div>

                <div className={`mt-4 font-mono text-xs leading-6 ${hasFailure ? "text-red-200/75" : "text-emerald-200/75"}`}>
                  {failureText}
                </div>
              </div>

              {errorLocations.length > 0 && (
                <div className="mt-4 space-y-3">
                  {errorLocations.map((location, index) => <SourceExcerpt key={`${location.file_path}-${location.line}-${index}`} location={location} />)}
                </div>
              )}

              <div className="mt-4 grid grid-cols-2 gap-px bg-white/[0.07] sm:grid-cols-4">
                <DataCell
                  label="TYPE"
                  value={String(lastAnalysis.error_type ?? "NONE")}
                />

                <DataCell
                  label="KNN"
                  value={knnLabel}
                />

                <DataCell
                  label="SOURCE"
                  value={lastAnalysis.error ? "BUILD/TEST" : "NONE"}
                />

                <DataCell
                  label="RETRY"
                  value={`${String(runState.healing_attempt ?? 0)} / ${String(runState.retry_limit ?? 5)}`}
                />
              </div>
            </div>

            <div className="bg-[#06090d] p-6 sm:p-8">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-mono text-[8px] tracking-[0.25em] text-cyan-300/60">
                    AI REPAIR
                  </div>

                  <h2 className="mt-2 text-xl font-semibold">
                    Generated recovery patch
                  </h2>
                </div>

                <Sparkles
                  size={18}
                  className="text-cyan-300/60"
                />
              </div>

              <div className="mt-6 overflow-hidden border border-white/[0.07] bg-[#030507]">
                <div className="border-b border-white/[0.06] px-4 py-3 font-mono text-[8px] text-white/25">
                  {filesChanged[0] ?? "No patch has been applied"}
                </div>

                <div className="p-4 font-mono text-[10px] leading-7">
                  <div className="text-cyan-200/75">
                    {String(runState.gemini_diagnosis ?? "Gemini diagnosis will appear after a repair attempt.")}
                  </div>
                  <div className="mt-3 text-white/30">
                    Changed: {filesChanged.length ? filesChanged.join(", ") : "none"}
                  </div>
                  <div className="mt-2 text-white/30">
                    Verification: {String(verification.status ?? "not run")}
                  </div>
                  <div className="mt-2 text-white/30">
                    Rollback: {String(record(runState.rollback).status ?? "not needed")}
                  </div>
                </div>

                <div className="flex gap-2 border-t border-white/[0.06] p-3">
                  <span className="font-mono text-[9px] text-white/35">
                    Patches are applied and verified only by the isolated worker.
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* TERMINAL                                                         */}
          {/* ---------------------------------------------------------------- */}

          <section
            id="execution-stream"
            className="mt-14 scroll-mt-24"
          >
            <SectionTitle
              eyebrow="EXECUTION STREAM"
              title="Live terminal"
              description="Real-time execution telemetry from the autonomous worker."
            />

            <div className="mt-5 border border-white/[0.07] bg-[#020304] shadow-[0_0_70px_rgba(0,0,0,0.3)]">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
                <div className="flex items-center gap-3">
                  <Terminal
                    size={15}
                    className="text-cyan-300"
                  />

                  <div>
                    <div className="text-xs font-medium">
                      ACR Worker / Run 024
                    </div>

                    <div className="font-mono text-[8px] text-white/20">
                      DOCKER EXECUTION
                      ENVIRONMENT
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      backendStatus ===
                      "connected"
                        ? "animate-pulse bg-emerald-400"
                        : "bg-red-400"
                    }`}
                  />

                  <span
                    className={`font-mono text-[8px] ${
                      backendStatus ===
                      "connected"
                        ? "text-emerald-300"
                        : "text-red-300"
                    }`}
                  >
                    {backendStatus ===
                    "connected"
                      ? pipelineRunning
                        ? "STREAMING"
                        : "READY"
                      : "OFFLINE"}
                  </span>
                </div>
              </div>

              <div className="max-h-[430px] overflow-y-auto p-5 font-mono text-[10px] leading-7">
                {liveLogs.length === 0 ? (
                  <>
                    <TerminalLine
                      time="--:--:--"
                      text="Waiting for backend execution events..."
                    />

                    <div className="mt-3 text-cyan-300">
                      <span>$</span>

                      <span className="ml-2">
                        acr-agent --watch
                      </span>

                      <span className="ml-1 animate-pulse">
                        ▌
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    {liveLogs.map(
                      (log) => (
                        <TerminalLine
                          key={log.id}
                          time={log.time}
                          text={log.text}
                          error={
                            log.type ===
                            "error"
                          }
                          success={
                            log.type ===
                            "success"
                          }
                        />
                      ),
                    )}

                    <div className="mt-3 text-cyan-300">
                      <span>$</span>

                      <span className="ml-2">
                        acr-agent --watch
                      </span>

                      <span className="ml-1 animate-pulse">
                        ▌
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>
          </section>

          <section className="mt-5 border border-white/[0.07] bg-[#06090d] p-6 sm:p-8">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center border border-cyan-400/20 bg-cyan-400/[0.05]">
                <MessageCircle size={17} className="text-cyan-300" />
              </div>
              <div>
                <div className="font-mono text-[8px] tracking-[0.22em] text-cyan-300/60">ACR_AGENT PIPELINE CHATBOT · LIVE RUN ONLY</div>
                <h2 className="mt-1 text-lg font-semibold">Ask ACR_AGENT about the live run</h2>
              </div>
            </div>
            <div className="mt-5 min-h-28 max-h-64 space-y-3 overflow-y-auto border border-white/[0.06] bg-black/20 p-4">
              {pipelineMessages.length === 0 ? (
                <p className="text-xs text-white/35">Ask naturally about failures, source lines, KNN, Gemini diagnosis, patches, rollback, retry attempts, or results. These answers are constrained to this browser session&apos;s actual worker state and logs.</p>
              ) : pipelineMessages.map((message) => (
                <div key={message.id} className={message.role === "user" ? "text-right" : "text-left"}>
                  <span className={`inline-block max-w-[90%] px-3 py-2 text-xs leading-5 ${message.role === "user" ? "bg-cyan-400/10 text-cyan-100" : "bg-white/[0.05] text-white/70"}`}>
                    {message.text}
                  </span>
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <input
                value={pipelineQuestion}
                onChange={(event) => setPipelineQuestion(event.target.value)}
                onKeyDown={(event) => { if (event.key === "Enter") askPipeline(); }}
                disabled={!assistantReady}
                maxLength={1500}
                placeholder="Ask about this run, for example: Which line failed?"
                className="h-10 min-w-0 flex-1 border border-white/[0.1] bg-black/25 px-3 text-xs text-white outline-none placeholder:text-white/25 focus:border-cyan-400/40 disabled:opacity-50"
              />
              <button type="button" onClick={askPipeline} disabled={!assistantReady || !pipelineQuestion.trim()} className="flex h-10 items-center gap-2 border border-cyan-400/20 bg-cyan-400/[0.08] px-3 text-xs text-cyan-200 disabled:opacity-40">
                <Send size={14} /> ASK
              </button>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3 font-mono text-[8px] tracking-[0.12em] text-white/30">
              <span>{assistantReady ? "LIVE RUN CONTEXT READY" : "AUTHORIZING RUN CONTEXT…"}</span>
              <span>PIPELINE DATA ONLY · NOT AURA</span>
            </div>
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* ARCHITECTURE / PULL REQUESTS                                    */}
          {/* ---------------------------------------------------------------- */}

          <section
            id="pull-requests-section"
            className="mt-14 scroll-mt-24"
          >
            <SectionTitle
              eyebrow="SYSTEM ARCHITECTURE"
              title="Inside the autonomous recovery loop"
              description="The core technologies responsible for detection, classification, repair and recovery."
            />

            <div className="relative mt-5 overflow-hidden border border-white/[0.07] bg-[#06090d] p-6 sm:p-10">
              <div className="grid gap-3 md:grid-cols-5">
                <ArchitectureCard
                  number="01"
                  icon={Github}
                  title="REPOSITORY"
                  description="GitHub source"
                />

                <ArchitectureCard
                  number="02"
                  icon={Container}
                  title="DOCKER"
                  description="Isolated runtime"
                />

                <ArchitectureCard
                  number="03"
                  icon={Cpu}
                  title="KNN"
                  description="Root cause"
                />

                <ArchitectureCard
                  number="04"
                  icon={Bot}
                  title="GEMINI"
                  description="Repair generation"
                />

                <ArchitectureCard
                  number="05"
                  icon={GitCommit}
                  title="RECOVERY"
                  description="Verified change"
                />
              </div>
            </div>

            <div className="mt-5 grid gap-px border border-white/[0.07] bg-white/[0.07] xl:grid-cols-2">
              <div className="bg-[#070b10] p-6 sm:p-8">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-mono text-[8px] tracking-[0.24em] text-red-300/65">AUTHORITATIVE FAILURE REVIEW</div>
                    <h3 className="mt-2 text-xl font-semibold">Detected source locations</h3>
                  </div>
                  {githubUrl && (
                    <a href={githubUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 border border-white/[0.1] bg-white/[0.03] px-3 py-2 font-mono text-[8px] tracking-[0.13em] text-white/75 transition hover:border-cyan-400/40 hover:text-cyan-200">
                      <Github size={13} /> {typeof runState.pr_link === "string" ? "VIEW PR ON GITHUB" : "VIEW SELECTED BRANCH"} <ArrowUpRight size={12} />
                    </a>
                  )}
                </div>
                {Boolean(runState.git_error) && (
                  <div className="mt-4 border border-amber-400/20 bg-amber-400/[0.05] px-3 py-2 font-mono text-[9px] leading-5 text-amber-100/75">
                    Build/test verification passed, but GitHub publishing was blocked: {String(runState.git_error)}
                  </div>
                )}
                <p className="mt-3 text-xs leading-6 text-white/35">Red lines are extracted from the current worker&apos;s actual compiler or test output. A healthy run has no failure locations.</p>
                <div className="mt-5 space-y-3">
                  {errorLocations.length > 0
                    ? errorLocations.map((location, index) => <SourceExcerpt key={`review-${location.file_path}-${location.line}-${index}`} location={location} compact />)
                    : <EmptyReview text="No source error is available for this run. Run a broken repository to see real compiler/test locations here." />}
                </div>
              </div>

              <div className="bg-[#06090d] p-6 sm:p-8">
                <div>
                  <div className="font-mono text-[8px] tracking-[0.24em] text-emerald-300/65">VERIFIED PATCH REVIEW</div>
                  <h3 className="mt-2 text-xl font-semibold">Removed and corrected code</h3>
                </div>
                <p className="mt-3 text-xs leading-6 text-white/35">Red `-` lines are the original code; green `+` lines are the exact candidate patch. A patch is marked verified only after a fresh build/test pass.</p>
                <div className="mt-5 space-y-3">
                  {patchDiffs.length > 0
                    ? patchDiffs.map((patch, index) => <PatchDiffViewer key={`${patch.file_path}-${index}`} patch={patch} />)
                    : <EmptyReview text="No repair patch was needed or applied in this run." />}
                </div>
              </div>
            </div>
          </section>

          <section className="mt-5 grid gap-px border border-cyan-400/15 bg-cyan-400/[0.04] sm:grid-cols-3">
            <DataCell
              label="TIME TAKEN"
              value={formatElapsedTime(elapsedSeconds)}
              change={pipelineRunning ? "RUNNING" : elapsedSeconds ? "MEASURED WORKER TIME" : "WAITING FOR RUN"}
            />
            <DataCell label="TIME BUDGET" value="04m 30s" change="HARD WORKER LIMIT" />
            <DataCell
              label="TIME STATUS"
              value={pipelineRunning ? "IN PROGRESS" : elapsedSeconds ? (elapsedSeconds < 300 ? "UNDER 05:00" : "LIMIT EXCEEDED") : "NOT STARTED"}
              change="AUTHORITATIVE RUN TELEMETRY"
            />
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* ADDITIONAL STATUS                                                */}
          {/* ---------------------------------------------------------------- */}

          <section className="mt-5 grid gap-5 lg:grid-cols-3">
            <StatusCard
              icon={Server}
              title="BACKEND"
              value={
                backendStatus ===
                "connected"
                  ? "ONLINE"
                  : "OFFLINE"
              }
              description="FastAPI service responding"
              progress={
                backendStatus ===
                "connected"
                  ? "96%"
                  : "35%"
              }
            />

            <StatusCard
              icon={Cpu}
              title="KNN ENGINE"
              value={knn.category ? "CLASSIFIED" : "STANDBY"}
              description={knn.category ? knnLabel : "No failure classification in this run"}
              progress={knn.confidence ? `${Math.round(Number(knn.confidence) * 100)}%` : "0%"}
            />

            <StatusCard
              icon={Sparkles}
              title="AI HEALING"
              value={runState.gemini_diagnosis ? "DIAGNOSED" : "STANDBY"}
              description={String(runState.gemini_diagnosis ?? "No Gemini diagnosis in this run")}
              progress={runState.gemini_diagnosis ? "100%" : "0%"}
            />
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* FOOTER                                                           */}
          {/* ---------------------------------------------------------------- */}

          <footer className="mt-14 border-t border-white/[0.07] py-7">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
              <div>
                <div className="font-mono text-[9px] tracking-[0.25em] text-white/30">
                  ACR_AGENT
                </div>

                <div className="mt-1 text-[9px] text-white/15">
                  Autonomous CI/CD
                  Healing System
                </div>
                <div className="mt-3 font-mono text-[9px] tracking-[0.12em] text-cyan-200/70">
                  Thank you for using ACR_AGENT.
                </div>
              </div>

              <div className="flex items-center gap-5 font-mono text-[8px] tracking-[0.18em] text-white/20">
                <span>AI</span>
                <span>KNN</span>
                <span>DOCKER</span>
                <span>GITHUB</span>
                <span>CI/CD</span>
              </div>
            </div>
          </footer>
        </div>
      </div>
    </main>
  );
}

/* -------------------------------------------------------------------------- */
/* TELEMETRY                                                                  */
/* -------------------------------------------------------------------------- */

function EmptyReview({ text }: { text: string }) {
  return <div className="border border-dashed border-white/[0.1] bg-black/20 p-4 text-xs leading-6 text-white/35">{text}</div>;
}

function SourceExcerpt({ location, compact = false }: { location: ErrorLocation; compact?: boolean }) {
  const lines = Array.isArray(location.lines) ? location.lines : [];
  return (
    <div className="overflow-hidden border border-red-400/15 bg-[#10080b]">
      <div className="flex items-center justify-between gap-3 border-b border-red-400/10 px-3 py-2 font-mono text-[9px] text-red-200/70">
        <span className="truncate">{location.file_path ?? "Unresolved source file"}</span>
        <span className="shrink-0">line {location.line ?? "?"}{location.column ? `:${location.column}` : ""}</span>
      </div>
      <pre className={`overflow-x-auto p-2 font-mono leading-6 text-white/65 ${compact ? "text-[10px]" : "text-xs"}`}>
        {lines.length > 0 ? lines.map((source) => (
          <div key={source.number} className={source.number === location.line ? "bg-red-400/20 text-red-100" : ""}>
            <span className="mr-3 inline-block w-8 select-none text-right text-white/25">{source.number}</span>
            <span>{source.content || " "}</span>
          </div>
        )) : <span className="text-white/35">The tool reported a file location but no safe excerpt could be read.</span>}
      </pre>
    </div>
  );
}

function PatchDiffViewer({ patch }: { patch: PatchDiff }) {
  const lines = String(patch.diff ?? "").split("\n").slice(0, 500);
  const status = String(patch.status ?? "CANDIDATE");
  return (
    <div className="overflow-hidden border border-emerald-400/15 bg-[#06100b]">
      <div className="flex items-center justify-between gap-3 border-b border-emerald-400/10 px-3 py-2 font-mono text-[9px]">
        <span className="truncate text-emerald-100/70">{patch.file_path ?? "Patched file"}</span>
        <span className={status === "VERIFIED" ? "text-emerald-300" : status === "ROLLED_BACK" ? "text-amber-300" : "text-cyan-300"}>{status}</span>
      </div>
      <pre className="max-h-72 overflow-auto p-2 font-mono text-[10px] leading-6">
        {lines.filter((line) => !line.startsWith("--- ") && !line.startsWith("+++ ")).map((line, index) => {
          const color = line.startsWith("+")
            ? "bg-emerald-400/15 text-emerald-100"
            : line.startsWith("-")
              ? "bg-red-400/15 text-red-100"
              : line.startsWith("@@")
                ? "text-cyan-200/60"
                : "text-white/45";
          return <div key={`${index}-${line}`} className={color}>{line || " "}</div>;
        })}
      </pre>
    </div>
  );
}

function Telemetry({
  label,
  value,
  status,
}: {
  label: string;
  value: string;
  status?: BackendStatus;
}) {
  const isOffline =
    status === "offline";

  const isConnecting =
    status === "connecting";

  return (
    <div className="mb-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span
          className={`h-1.5 w-1.5 rounded-full ${
            isOffline
              ? "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.7)]"
              : isConnecting
                ? "animate-pulse bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
                : "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
          }`}
        />

        <span className="font-mono text-[8px] text-white/30">
          {label}
        </span>
      </div>

      <span
        className={`font-mono text-[8px] ${
          isOffline
            ? "text-red-400/70"
            : isConnecting
              ? "text-amber-400/70"
              : "text-emerald-400/70"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* CORE NODE                                                                  */
/* -------------------------------------------------------------------------- */

function CoreNode({
  icon: Icon,
  label,
  position,
}: {
  icon: LucideIcon;
  label: string;
  position: string;
}) {
  return (
    <div
      className={`absolute ${position} flex items-center gap-2 border border-white/[0.08] bg-black/60 px-3 py-2 backdrop-blur-md`}
    >
      <Icon
        size={11}
        className="text-cyan-300/80"
      />

      <span className="font-mono text-[7px] tracking-[0.18em] text-white/40">
        {label}
      </span>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* METRIC                                                                     */
/* -------------------------------------------------------------------------- */

function Metric({
  label,
  value,
  change,
}: {
  label: string;
  value: string;
  change: string;
}) {
  return (
    <div className="border-r border-white/[0.06] p-4 last:border-r-0 sm:p-5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[8px] tracking-[0.16em] text-white/25">
          {label}
        </span>

        <span className="font-mono text-[8px] text-emerald-400/70">
          {change}
        </span>
      </div>

      <div className="mt-4 text-2xl font-semibold tracking-tight">
        {value}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* MINI STAT                                                                  */
/* -------------------------------------------------------------------------- */

function MiniStat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="font-mono text-[7px] tracking-[0.18em] text-white/20">
        {label}
      </div>

      <div className="mt-1 text-sm font-semibold text-white/75">
        {value}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* SECTION TITLE                                                              */
/* -------------------------------------------------------------------------- */

function SectionTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div>
      <div className="font-mono text-[8px] tracking-[0.3em] text-cyan-300/55">
        {eyebrow}
      </div>

      <h2 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
        {title}
      </h2>

      {description && (
        <p className="mt-2 max-w-2xl text-xs leading-6 text-white/30 sm:text-sm">
          {description}
        </p>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* TEAM MEMBER                                                                */
/* -------------------------------------------------------------------------- */

function TeamMember({
  label,
  name,
}: {
  label: string;
  name: string;
}) {
  return (
    <div className="border-l border-white/[0.06] p-6 transition hover:bg-white/[0.015]">
      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-white/[0.08] bg-white/[0.025]">
        <User
          size={19}
          className="text-white/30"
        />
      </div>

      <div className="mt-5 font-mono text-[8px] tracking-[0.2em] text-white/25">
        {label}
      </div>

      <div className="mt-2 text-sm text-white/50">
        {name}
      </div>

      <div className="mt-4 h-px bg-white/[0.05]" />

      <div className="mt-4 flex items-center gap-2 font-mono text-[7px] tracking-wider text-white/15">
        <Circle
          size={5}
          className="fill-emerald-400 text-emerald-400"
        />

        PROFILE ACTIVE
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* DATA CELL                                                                  */
/* -------------------------------------------------------------------------- */

function DataCell({
  label,
  value,
  change,
}: {
  label: string;
  value: string;
  change?: string;
}) {
  return (
    <div className="bg-[#05080c] p-3">
      <div className="font-mono text-[7px] tracking-wider text-white/20">
        {label}
      </div>

      <div className="mt-2 font-mono text-[9px] text-white/55">
        {value}
      </div>

      {change && (
        <div className="mt-1 font-mono text-[7px] tracking-wider text-cyan-300/60">
          {change}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* TERMINAL LINE                                                              */
/* -------------------------------------------------------------------------- */

function TerminalLine({
  time,
  text,
  error,
  success,
}: {
  time: string;
  text: string;
  error?: boolean;
  success?: boolean;
}) {
  return (
    <div className="flex gap-4">
      <span className="shrink-0 text-white/15">
        [{time}]
      </span>

      <span
        className={
          error
            ? "text-red-300/75"
            : success
              ? "text-emerald-300"
              : "text-white/40"
        }
      >
        {success && (
          <Check
            size={11}
            className="mr-1 inline"
          />
        )}

        {text}
      </span>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* ARCHITECTURE CARD                                                          */
/* -------------------------------------------------------------------------- */

function ArchitectureCard({
  number,
  icon: Icon,
  title,
  description,
}: {
  number: string;
  icon: LucideIcon;
  title: string;
  description: string;
}) {
  return (
    <div className="group relative border border-white/[0.07] bg-white/[0.02] p-5 transition-all duration-300 hover:-translate-y-1 hover:border-cyan-400/20 hover:bg-cyan-400/[0.025] hover:shadow-[0_10px_40px_rgba(34,211,238,0.05)]">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[8px] text-white/15">
          {number}
        </span>

        <Icon
          size={16}
          className="text-cyan-300/50"
        />
      </div>

      <div className="mt-8 font-mono text-[9px] tracking-[0.18em] text-white/55">
        {title}
      </div>

      <div className="mt-2 text-[10px] text-white/25">
        {description}
      </div>

      <ArrowRight
        size={10}
        className="absolute bottom-4 right-4 text-white/10 transition group-hover:translate-x-1 group-hover:text-cyan-300/60"
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* STATUS CARD                                                                */
/* -------------------------------------------------------------------------- */

function StatusCard({
  icon: Icon,
  title,
  value,
  description,
  progress,
}: {
  icon: LucideIcon;
  title: string;
  value: string;
  description: string;
  progress: string;
}) {
  return (
    <div className="group border border-white/[0.07] bg-[#06090d] p-6 transition hover:border-cyan-400/15">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center border border-cyan-400/10 bg-cyan-400/[0.04]">
            <Icon
              size={15}
              className="text-cyan-300/70"
            />
          </div>

          <span className="font-mono text-[8px] tracking-[0.2em] text-white/30">
            {title}
          </span>
        </div>

        <CheckCircle2
          size={15}
          className="text-emerald-400/60"
        />
      </div>

      <div className="mt-6 flex items-end justify-between">
        <div>
          <div className="text-xl font-semibold">
            {value}
          </div>

          <div className="mt-1 text-[10px] text-white/25">
            {description}
          </div>
        </div>

        <div className="font-mono text-[9px] text-cyan-300/60">
          {progress}
        </div>
      </div>

      <div className="mt-5 h-1 overflow-hidden bg-white/[0.05]">
        <div
          className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400 transition-all duration-700 group-hover:shadow-[0_0_15px_rgba(34,211,238,0.5)]"
          style={{
            width: progress,
          }}
        />
      </div>
    </div>
  );
}

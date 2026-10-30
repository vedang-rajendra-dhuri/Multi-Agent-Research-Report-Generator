import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, BookOpenCheck, Check, CircleAlert, FolderOpen, LoaderCircle, LockKeyhole, Plus, Search, ShieldCheck } from "lucide-react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  authApi,
  checkReadiness,
  projectsApi,
  setAccessToken,
  type ResearchTask,
  type User,
} from "./api/client";
import LiveWorkspace from "./pages/LiveWorkspace";
import Analytics from "./pages/Analytics";
import Library from "./pages/Library";
import NewResearch from "./pages/NewResearch";

type AuthMode = "login" | "register";
const authFormSchema = (mode: AuthMode) =>
  z
    .object({
      full_name: z.string().trim().max(160).optional(),
      email: z.string().trim().email("Enter a valid email address.").max(320),
      password: z.string().min(1).max(128),
    })
    .superRefine((values, context) => {
      if (mode === "register") {
        if (!values.full_name) {
          context.addIssue({
            code: "custom",
            path: ["full_name"],
            message: "Enter your name.",
          });
        }
        if (values.password.length < 12) {
          context.addIssue({
            code: "custom",
            path: ["password"],
            message: "Use at least 12 characters.",
          });
        }
      }
    });

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<AuthMode>("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState<boolean | null>(null);
  const [restoring, setRestoring] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const taskId = location.pathname.match(/^\/tasks\/([0-9a-f-]+)$/i)?.[1] ?? null;
  const selectedProjectId = new URLSearchParams(location.search).get("project") ?? undefined;
  const page = taskId
    ? "task"
    : location.pathname === "/research"
      ? "new-research"
      : location.pathname === "/library"
        ? "library"
        : location.pathname === "/analytics"
          ? "analytics"
        : "overview";
  const queryClient = useQueryClient();
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(),
    enabled: Boolean(user && ready),
  });
  const createProject = useMutation({
    mutationFn: projectsApi.create,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  const archiveProject = useMutation({
    mutationFn: projectsApi.archive,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  function openTask(task: ResearchTask) {
    navigate(`/tasks/${task.id}`);
  }

  function backToOverview() {
    navigate("/");
  }
  const {
    register: bindField,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(authFormSchema(mode)),
  });

  useEffect(() => {
    let active = true;
    void checkReadiness().then((result) => {
      if (active) setReady(result);
    });
    if (!document.cookie.includes("csrf_token=")) {
      setRestoring(false);
      return () => {
        active = false;
      };
    }
    void authApi
      .refresh()
      .then((result) => {
        if (active) {
          setAccessToken(result.access_token);
          setUser(result.user);
        }
      })
      .catch(() => {
        setAccessToken(null);
      })
      .finally(() => {
        if (active) setRestoring(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function submit(values: {
    full_name?: string;
    email: string;
    password: string;
  }) {
    setBusy(true);
    setError("");
    try {
      const result =
        mode === "register"
          ? await authApi.register({
              email: values.email,
              password: values.password,
              full_name: values.full_name ?? "",
            })
          : await authApi.login({ email: values.email, password: values.password });
      setAccessToken(result.access_token);
      setUser(result.user);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to complete sign-in.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError("");
    try {
      await authApi.logout();
      setAccessToken(null);
      setUser(null);
      queryClient.removeQueries({ queryKey: ["projects"] });
      backToOverview();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign out.");
    } finally {
      setBusy(false);
    }
  }

  if (restoring) {
    return <main className="loading-screen"><LoaderCircle className="spin" /> Restoring your secure session…</main>;
  }

  if (user) {
    return (
      <main className="app-shell">
        <aside className="sidebar">
          <div className="brand"><span className="brand-mark"><BookOpenCheck size={19} /></span><span>Report<b>Pilot</b></span></div>
          <div className="nav-label">WORKSPACE</div>
          <button className={`nav-item ${page === "overview" ? "active" : ""}`} onClick={backToOverview}><Search size={17} /> Overview</button>
          <button className={`nav-item ${page === "analytics" ? "active" : ""}`} onClick={() => navigate("/analytics")}><BarChart3 size={17} /> Analytics</button>
          <button className={`nav-item ${page === "new-research" ? "active" : ""}`} onClick={() => navigate("/research")}><BookOpenCheck size={17} /> New Research</button>
          <button className={`nav-item ${page === "library" ? "active" : ""}`} onClick={() => navigate("/library")}><FolderOpen size={17} /> Library</button>
          <div className="sidebar-note">Research requires hosted PostgreSQL, a configured LLM provider, and Tavily search credentials.</div>
          <div className="profile"><div className="avatar">{user.full_name.slice(0, 1).toUpperCase()}</div><div className="profile-copy"><strong>{user.full_name}</strong><span>{user.email}</span></div><button className="quiet-button" onClick={signOut} disabled={busy}>Sign out</button></div>
        </aside>
        <section className="workspace">
          <header className="topbar"><span>{page === "task" ? "Live workspace" : page === "new-research" ? "New research" : page === "library" ? "Research library" : page === "analytics" ? "Workspace analytics" : "Overview"}</span><span className="secure-label"><ShieldCheck size={15} /> Private workspace</span></header>
          {page === "task" && taskId ? (
            <div className="dashboard"><LiveWorkspace taskId={taskId} onBack={backToOverview} /></div>
          ) : page === "new-research" ? (
            <div className="dashboard"><NewResearch projects={projectsQuery.data?.items ?? []} initialProjectId={selectedProjectId} onStarted={openTask} onCancel={backToOverview} /></div>
          ) : page === "library" ? (
            <div className="dashboard"><Library onOpen={openTask} /></div>
          ) : page === "analytics" ? (
            <div className="dashboard analytics-dashboard">
              <Analytics onOpen={(id) => navigate(`/tasks/${encodeURIComponent(id)}`)} />
            </div>
          ) : (
          <div className="dashboard">
            <div className="welcome-row"><div><p className="eyebrow">YOUR RESEARCH WORKSPACE</p><h1>Welcome, {user.full_name.split(" ")[0]}</h1><p className="subtitle">Your research workspace is ready for its next setup step.</p></div><div className={`service-status ${ready ? "online" : "offline"}`}><span className="status-dot" />{ready ? "Services connected" : "Setup required"}</div></div>
            {error && <div className="alert" role="alert"><CircleAlert size={18} />{error}</div>}
            {!ready && <div className="setup-card"><div className="setup-icon"><LockKeyhole size={21} /></div><div className="setup-copy"><h2>Finish connecting your workspace</h2><p>A hosted PostgreSQL connection is required before projects and research can be saved.</p><div className="setup-check"><Check size={16} /> Account authenticated</div><div className="setup-check pending"><CircleAlert size={16} /> Hosted database not connected</div></div></div>}
            {ready && <section className="projects-card">
              <div className="projects-heading"><div><p className="eyebrow">YOUR WORK</p><h2>Research projects</h2></div><span className="project-count">{projectsQuery.data?.total ?? 0}</span></div>
              <button className="new-research-link" onClick={() => navigate("/research")}><Plus size={16} /> New Research</button>
              <form className="project-form" onSubmit={(event) => {
                event.preventDefault();
                const formElement = event.currentTarget;
                const form = new FormData(formElement);
                const title = String(form.get("project_title") ?? "").trim();
                if (!title) return;
                createProject.mutate({ title }, { onSuccess: () => formElement.reset() });
              }}>
                <input name="project_title" aria-label="Project title" placeholder="Give your project a title" required maxLength={200} />
                <button className="primary-button" type="submit" disabled={createProject.isPending}><Plus size={17} />Create project</button>
              </form>
              {createProject.isError && <div className="alert" role="alert"><CircleAlert size={17} />{createProject.error.message}</div>}
              {projectsQuery.isError && <div className="alert" role="alert"><CircleAlert size={17} />Unable to load projects: {projectsQuery.error.message}</div>}
              {projectsQuery.isLoading && <p className="empty-projects">Loading saved projects…</p>}
              {!projectsQuery.isLoading && !projectsQuery.isError && projectsQuery.data?.items.length === 0 && <p className="empty-projects">No projects yet. Create one to start organizing your research.</p>}
              <div className="project-list">{projectsQuery.data?.items.map((project) => <article className="project-row" key={project.id}><div className="project-badge"><BookOpenCheck size={17} /></div><div className="project-info"><strong>{project.title}</strong><span>{project.description || "No description"} · Updated {new Date(project.updated_at).toLocaleDateString()}</span></div><button className="quiet-button project-action" onClick={() => navigate(`/research?project=${encodeURIComponent(project.id)}`)}>Research</button><button className="quiet-button project-action" disabled={archiveProject.isPending} onClick={() => archiveProject.mutate(project.id)}>Archive</button></article>)}</div>
              {archiveProject.isError && <div className="alert" role="alert"><CircleAlert size={17} />Unable to archive project: {archiveProject.error.message}</div>}
            </section>}
            <div className="next-card"><div><p className="eyebrow">NEXT STEP</p><h2>Evidence-grounded research</h2><p>Once configured, research tasks will run through traceable planning, source discovery, analysis, verification, and human review.</p></div><ArrowRight size={20} /></div>
            <p className="disclaimer">AI-generated research can contain errors. Review sources and evidence before relying on any report.</p>
          </div>
          )}
        </section>
      </main>
    );
  }

  return (
    <main className="auth-page">
      <section className="auth-aside">
        <div className="brand light-brand"><span className="brand-mark"><BookOpenCheck size={19} /></span><span>Report<b>Pilot</b></span></div>
        <div className="aside-message"><div className="eyebrow">RESEARCH WITH CLARITY</div><h1>From complex questions to evidence you can inspect.</h1><p>Build structured reports from real sources, with traceable citations and human review.</p><div className="aside-points"><span><Check size={16} /> Source-grounded workflows</span><span><Check size={16} /> Transparent claim verification</span><span><Check size={16} /> Human approval at every finish line</span></div></div>
        <div className="aside-foot">AI-generated research requires human review.</div>
      </section>
      <section className="auth-main">
        <div className="auth-card">
          <p className="eyebrow">{mode === "login" ? "WELCOME BACK" : "GET STARTED"}</p>
          <h2>{mode === "login" ? "Sign in to your account" : "Create your account"}</h2>
          <p className="auth-description">Secure access to your private research workspace.</p>
          {error && <div className="alert" role="alert"><CircleAlert size={18} />{error}</div>}
          <form onSubmit={handleSubmit(submit)}>
            {mode === "register" && <label>Full name<input {...bindField("full_name")} autoComplete="name" maxLength={160} />{errors.full_name && <small className="field-error">{errors.full_name.message}</small>}</label>}
            <label>Email address<input {...bindField("email")} type="email" autoComplete="email" maxLength={320} />{errors.email && <small className="field-error">{errors.email.message}</small>}</label>
            <label>Password<input {...bindField("password")} type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} maxLength={128} />{errors.password && <small className="field-error">{errors.password.message}</small>}{mode === "register" && !errors.password && <small>Use at least 12 characters.</small>}</label>
            <button className="primary-button" type="submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : null}{mode === "login" ? "Sign in" : "Create account"}<ArrowRight size={17} /></button>
          </form>
          <p className="mode-toggle">{mode === "login" ? "New to ReportPilot?" : "Already have an account?"} <button onClick={() => { setError(""); reset(); setMode(mode === "login" ? "register" : "login"); }}>{mode === "login" ? "Create an account" : "Sign in"}</button></p>
          <div className="form-status"><span className={`status-dot ${ready ? "green-dot" : ""}`} />{ready ? "Backend and database are ready" : "Backend setup is incomplete or unavailable"}</div>
        </div>
      </section>
    </main>
  );
}
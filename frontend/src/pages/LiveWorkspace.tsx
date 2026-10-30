import { useEffect, useState } from "react";
import { ArrowLeft, CircleAlert, LoaderCircle, Radio, ShieldCheck, XCircle } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReportEditor from "./ReportEditor";
import { downloadApprovedReport, researchApi, streamTaskEvents, type TaskEvent } from "../api/client";

interface LiveWorkspaceProps {
  taskId: string;
  onBack: () => void;
}

const terminalStatuses = new Set(["waiting_review", "completed", "failed", "cancelled"]);

export default function LiveWorkspace({ taskId, onBack }: LiveWorkspaceProps) {
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [streamError, setStreamError] = useState("");
  const [reviewError, setReviewError] = useState("");
  const queryClient = useQueryClient();
  const taskQuery = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => researchApi.task(taskId),
    refetchInterval: (query) =>
      terminalStatuses.has(query.state.data?.status ?? "") ? false : 2000,
  });
  const cancelTask = useMutation({
    mutationFn: () => researchApi.cancel(taskId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["task", taskId] });
    },
  });
  const resumeTask = useMutation({
    mutationFn: () => researchApi.resume(taskId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["task", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task-history"] }),
      ]);
    },
  });
  const reportQuery = useQuery({
    queryKey: ["report", taskId],
    queryFn: () => researchApi.report(taskId),
    enabled: taskQuery.data?.status === "waiting_review" || taskQuery.data?.status === "completed",
    refetchInterval: (query) =>
      ["pending", "running"].includes(query.state.data?.version.verification_status ?? "")
        ? 2000
        : false,
  });
  const review = useMutation({
    mutationFn: (input: { decision: "approved" | "rejected"; comment?: string }) =>
      researchApi.review(reportQuery.data!.id, {
        decision: input.decision,
        comment: input.comment,
      }),
    onSuccess: async () => {
      setReviewError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["report", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task", taskId] }),
      ]);
    },
    onError: (reason) => {
      setReviewError(reason instanceof Error ? reason.message : "Unable to save review decision.");
    },
  });
  const revise = useMutation({
    mutationFn: (input: Parameters<typeof researchApi.revise>[1]) =>
      researchApi.revise(reportQuery.data!.id, input),
    onSuccess: async () => {
      setReviewError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["report", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task", taskId] }),
        queryClient.invalidateQueries({ queryKey: ["task-history"] }),
      ]);
    },
    onError: (reason) => {
      setReviewError(reason instanceof Error ? reason.message : "Unable to save report revision.");
    },
  });
  const retryVerification = useMutation({
    mutationFn: () =>
      researchApi.retryVerification(reportQuery.data!.id, reportQuery.data!.current_version),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report", taskId] });
    },
    onError: (reason) => {
      setReviewError(reason instanceof Error ? reason.message : "Unable to retry verification.");
    },
  });
  const exportReport = useMutation({
    mutationFn: (format: "markdown" | "pdf" | "docx") =>
      downloadApprovedReport(reportQuery.data!.id, format),
    onError: (reason) => {
      setReviewError(reason instanceof Error ? reason.message : "Unable to export report.");
    },
  });

  useEffect(() => {
    const controller = new AbortController();
    void streamTaskEvents(taskId, (event) => {
      setEvents((current) => [...current.slice(-99), event]);
      void queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      void queryClient.invalidateQueries({ queryKey: ["report", taskId] });
    }, controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setStreamError(reason instanceof Error ? reason.message : "Task event stream disconnected.");
      }
    });
    return () => controller.abort();
  }, [queryClient, taskId]);

  const task = taskQuery.data;
  const canCancel = task?.status === "queued" || task?.status === "running";
  const report = reportQuery.data;

  return (
    <section className="live-card">
      <button className="back-button" onClick={onBack}>
        <ArrowLeft size={16} /> Back to projects
      </button>
      <div className="live-heading">
        <div>
          <p className="eyebrow">LIVE RESEARCH TASK</p>
          <h2>{task ? `Research ${task.status.replace("_", " ")}` : "Loading task…"}</h2>
          <p className="task-id">Task ID: {taskId}</p>
        </div>
        {canCancel && (
          <button
            className="cancel-button"
            disabled={cancelTask.isPending}
            onClick={() => cancelTask.mutate()}
          >
            <XCircle size={16} /> Cancel task
          </button>
        )}
      </div>
      {taskQuery.isLoading && <p className="empty-projects"><LoaderCircle className="spin" size={17} /> Loading task status…</p>}
      {taskQuery.isError && <div className="alert" role="alert"><CircleAlert size={18} />{taskQuery.error.message}</div>}
      {task?.status === "failed" && (
        <div className="alert" role="alert">
          <CircleAlert size={18} />
          <span>
            Research stopped. Error code: {task.safe_error_code ?? "unknown"}.
            {task.attempt_count < 3 && (
              <button
                className="quiet-button"
                disabled={resumeTask.isPending}
                onClick={() => resumeTask.mutate()}
              >
                {resumeTask.isPending && <LoaderCircle className="spin" size={15} />}
                Retry research
              </button>
            )}
          </span>
        </div>
      )}
      {resumeTask.isError && <div className="alert" role="alert"><CircleAlert size={18} />Unable to retry research: {resumeTask.error.message}</div>}
      {task?.status === "waiting_review" && (
        <div className="setup-card review-ready">
          <div className="setup-icon"><ShieldCheck size={21} /></div>
          <div className="setup-copy">
            <h2>Draft ready for review</h2>
            <p>The report has been generated from retrieved evidence. Review its citations and verification assessments before deciding.</p>
          </div>
        </div>
      )}
      {cancelTask.isError && <div className="alert" role="alert"><CircleAlert size={18} />{cancelTask.error.message}</div>}
      {streamError && <div className="stream-notice"><Radio size={16} />Live updates disconnected: {streamError}. Task status will continue to refresh.</div>}
      {reportQuery.isLoading && task?.status === "waiting_review" && <p className="empty-projects"><LoaderCircle className="spin" size={17} /> Loading persisted report…</p>}
      {reportQuery.isError && task?.status === "waiting_review" && <div className="alert" role="alert"><CircleAlert size={18} />Unable to load report: {reportQuery.error.message}</div>}
      {report && (
        <ReportEditor
          report={report}
          busy={review.isPending || revise.isPending || retryVerification.isPending || exportReport.isPending}
          error={reviewError}
          onReview={(decision, comment) =>
            review.mutate({ decision, comment })
          }
          onExport={(format) => exportReport.mutate(format)}
          onReverify={() => retryVerification.mutate()}
          onRevise={async (revision) => {
            try {
              await revise.mutateAsync(revision);
              return true;
            } catch {
              return false;
            }
          }}
        />
      )}
      <div className="event-panel">
        <div className="event-panel-heading"><strong>Workflow events</strong><span>{events.length} received</span></div>
        {events.length === 0 ? (
          <p className="empty-projects">Waiting for persisted workflow events…</p>
        ) : (
          <ol className="event-list">
            {events.map((event, index) => (
              <li key={`${event.timestamp}-${event.type}-${index}`}>
                <span className={`event-marker ${event.type.endsWith("failed") ? "failed" : ""}`} />
                <div><strong>{event.agent ?? "Research task"} · {event.type.replace(/\./g, " ")}</strong><span>{event.stage ? `Stage: ${event.stage} · ` : ""}{new Date(event.timestamp).toLocaleTimeString()}</span></div>
              </li>
            ))}
          </ol>
        )}
      </div>
      <p className="disclaimer">Research progress reflects events persisted by the worker. AI assessments do not guarantee factual accuracy; review the sources and report before relying on it.</p>
    </section>
  );
}

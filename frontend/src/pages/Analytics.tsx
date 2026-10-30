import { useState } from "react";
import { Activity, AlertCircle, CheckCircle2, Clock3, RefreshCw, ShieldCheck } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi, type ResearchTask } from "../api/client";

interface AnalyticsProps {
  onOpen: (taskId: string) => void;
}

const periods = [7, 30, 90] as const;
const statusNames: Record<ResearchTask["status"], string> = {
  queued: "Queued",
  running: "Running",
  waiting_review: "Awaiting review",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

function formatDay(value: string, options?: Intl.DateTimeFormatOptions): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, options ?? {
    month: "short",
    day: "numeric",
  });
}

export default function Analytics({ onOpen }: AnalyticsProps) {
  const [days, setDays] = useState<(typeof periods)[number]>(30);
  const [statusFilter, setStatusFilter] = useState<ResearchTask["status"] | null>(null);
  const analyticsQuery = useQuery({
    queryKey: ["workspace-analytics", days],
    queryFn: () => analyticsApi.workspace(days),
    staleTime: 30_000,
  });
  const analytics = analyticsQuery.data;
  const maxDailyTasks = Math.max(1, ...(analytics?.daily_tasks.map((entry) => entry.total) ?? []));
  const visibleTasks = (analytics?.recent_tasks ?? []).filter(
    (task) => statusFilter === null || task.status === statusFilter,
  );
  const taskStatus = (analytics?.tasks_by_status ?? []).filter(({ count }) => count > 0);
  const approvedReports = analytics?.reports_by_status.find(({ status }) => status === "approved")?.count ?? 0;
  const awaitingReview = analytics?.reports_by_status.find(({ status }) => status === "pending")?.count ?? 0;

  return (
    <section className="analytics-page">
      <div className="analytics-heading">
        <div>
          <p className="eyebrow">YOUR WORKSPACE</p>
          <h1>Research analytics</h1>
          <p>Track progress, source coverage, and reports across your projects.</p>
        </div>
        <div className="analytics-controls">
          <div className="period-picker" role="group" aria-label="Analytics time range">
            {periods.map((period) => (
              <button
                key={period}
                type="button"
                aria-pressed={days === period}
                className={days === period ? "selected" : ""}
                onClick={() => setDays(period)}
              >
                {period} days
              </button>
            ))}
          </div>
          <button
            type="button"
            className="analytics-refresh"
            onClick={() => void analyticsQuery.refetch()}
            disabled={analyticsQuery.isFetching}
            aria-label="Refresh analytics"
          >
            <RefreshCw className={analyticsQuery.isFetching ? "spin" : ""} size={15} />
            Refresh
          </button>
        </div>
      </div>

      {analyticsQuery.isLoading && <p className="analytics-message">Loading workspace insights…</p>}
      {analyticsQuery.isError && (
        <div className="alert" role="alert">
          <AlertCircle size={18} />
          Unable to load analytics: {analyticsQuery.error.message}
          <button type="button" className="quiet-button" onClick={() => void analyticsQuery.refetch()}>
            Try again
          </button>
        </div>
      )}

      {analytics && (
        <>
          <div className="analytics-metrics">
            <article className="metric-card">
              <span className="metric-icon blue"><Activity size={18} /></span>
              <span>Research tasks</span>
              <strong>{analytics.tasks_total}</strong>
              <small>in the last {days} days</small>
            </article>
            <article className="metric-card">
              <span className="metric-icon green"><CheckCircle2 size={18} /></span>
              <span>Approved reports</span>
              <strong>{approvedReports}</strong>
              <small>{awaitingReview} waiting for review</small>
            </article>
            <article className="metric-card">
              <span className="metric-icon violet"><ShieldCheck size={18} /></span>
              <span>Sources collected</span>
              <strong>{analytics.sources_total}</strong>
              <small>linked to research tasks</small>
            </article>
            <article className="metric-card">
              <span className="metric-icon amber"><Clock3 size={18} /></span>
              <span>Active projects</span>
              <strong>{analytics.projects_active}</strong>
              <small>{analytics.projects_total} total projects</small>
            </article>
          </div>

          <div className="analytics-grid">
            <section className="analytics-card activity-card">
              <div className="analytics-card-heading">
                <div>
                  <h2>Research activity</h2>
                  <p>Tasks created per day · UTC</p>
                </div>
                <span className="chart-legend"><i /> Tasks</span>
              </div>
              {analytics.tasks_total === 0 ? (
                <p className="analytics-empty">No research activity in this period yet.</p>
              ) : (
                <div className={`activity-chart ${days > 7 ? "dense" : ""}`} role="img" aria-label={`Daily research task activity for the last ${days} days`}>
                  {analytics.daily_tasks.map((entry, index) => {
                    const height = Math.max(entry.total ? 8 : 2, (entry.total / maxDailyTasks) * 100);
                    const showLabel = days === 7 || index % (days === 30 ? 5 : 15) === 0 || index === days - 1;
                    return (
                      <div className="chart-column" key={entry.day}>
                        <div className="chart-track" title={`${formatDay(entry.day)}: ${entry.total} tasks, ${entry.failed} failed`}>
                          <span
                            className={`chart-bar ${entry.failed > 0 ? "has-failures" : ""}`}
                            style={{ height: `${height}%` }}
                          />
                        </div>
                        {showLabel && <small>{formatDay(entry.day, { month: "numeric", day: "numeric" })}</small>}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="analytics-card status-card">
              <div className="analytics-card-heading">
                <div>
                  <h2>Task status</h2>
                  <p>Select a status to filter recent work</p>
                </div>
              </div>
              {taskStatus.length === 0 ? (
                <p className="analytics-empty">Task status will appear after your first research run.</p>
              ) : (
                <div className="status-breakdown">
                  {taskStatus.map(({ status, count }) => (
                    <button
                      type="button"
                      key={status}
                      className={`status-filter ${statusFilter === status ? "active" : ""}`}
                      aria-pressed={statusFilter === status}
                      onClick={() => setStatusFilter(statusFilter === status ? null : status)}
                    >
                      <span className={`status-marker ${status}`} />
                      <span>{statusNames[status]}</span>
                      <strong>{count}</strong>
                    </button>
                  ))}
                </div>
              )}
            </section>
          </div>

          <section className="analytics-card recent-activity">
            <div className="analytics-card-heading">
              <div>
                <h2>Recent research</h2>
                <p>{statusFilter ? `Filtered by ${statusNames[statusFilter].toLowerCase()}` : "Latest activity across your projects"}</p>
              </div>
              <span className="activity-count">{visibleTasks.length} shown</span>
            </div>
            {visibleTasks.length === 0 ? (
              <p className="analytics-empty">
                {analytics.recent_tasks.length ? "No recent tasks match this status." : "Your recent research tasks will show up here."}
              </p>
            ) : (
              <div className="recent-task-list">
                {visibleTasks.map((task) => (
                  <button
                    className="recent-task"
                    type="button"
                    key={task.id}
                    onClick={() => onOpen(task.id)}
                  >
                    <span className="recent-task-mark"><Activity size={16} /></span>
                    <span className="recent-task-copy">
                      <strong>{task.project_title}</strong>
                      <small>{new Date(task.created_at).toLocaleString()} · Task {task.id.slice(0, 8)}</small>
                    </span>
                    <span className={`task-status ${task.status}`}>{statusNames[task.status]}</span>
                  </button>
                ))}
              </div>
            )}
          </section>
          <p className="analytics-footnote">
            Showing task and report activity for the last {days} calendar days. Project totals include archived projects.
          </p>
        </>
      )}
    </section>
  );
}

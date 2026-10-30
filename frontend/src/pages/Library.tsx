import { useState } from "react";
import { ArrowRight, CircleAlert, LoaderCircle, Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { projectsApi, researchApi, type ResearchTask } from "../api/client";

interface LibraryProps {
  onOpen: (task: ResearchTask) => void;
}

const pageSize = 20;

export default function Library({ onOpen }: LibraryProps) {
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState("");
  const tasksQuery = useQuery({
    queryKey: ["task-history", page],
    queryFn: () => researchApi.listTasks(pageSize, page * pageSize),
  });
  const projectsQuery = useQuery({
    queryKey: ["projects", "all"],
    queryFn: () => projectsApi.list(null),
  });
  const projectTitles = new Map(
    (projectsQuery.data?.items ?? []).map((project) => [project.id, project.title]),
  );
  const normalizedFilter = filter.trim().toLowerCase();
  const tasks = (tasksQuery.data?.items ?? []).filter((task) => {
    if (!normalizedFilter) return true;
    return [
      task.status,
      task.current_stage ?? "",
      task.safe_error_code ?? "",
      task.id,
      projectTitles.get(task.project_id) ?? "",
    ].some((value) => value.toLowerCase().includes(normalizedFilter));
  });
  const pageCount = Math.max(1, Math.ceil((tasksQuery.data?.total ?? 0) / pageSize));

  return (
    <section className="library-card">
      <div className="library-heading">
        <div>
          <p className="eyebrow">YOUR WORK</p>
          <h2>Research library</h2>
          <p>Browse saved research tasks and reopen reports for review or export.</p>
        </div>
        <label className="library-search">
          <Search size={16} />
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="Search this page's projects, status, or task ID"
            aria-label="Search research history"
          />
        </label>
      </div>
      {(tasksQuery.isLoading || projectsQuery.isLoading) && (
        <p className="empty-projects"><LoaderCircle className="spin" size={17} /> Loading saved research…</p>
      )}
      {tasksQuery.isError && (
        <div className="alert" role="alert"><CircleAlert size={18} />Unable to load research history: {tasksQuery.error.message}</div>
      )}
      {projectsQuery.isError && (
        <div className="alert" role="alert"><CircleAlert size={18} />Unable to load project names: {projectsQuery.error.message}</div>
      )}
      {!tasksQuery.isLoading && !tasksQuery.isError && tasksQuery.data?.total === 0 && (
        <p className="empty-projects">No saved research tasks yet. Start a research brief to see it here.</p>
      )}
      {tasks.length > 0 && (
        <>
          <div className="library-list">
            {tasks.map((task) => (
              <article className="library-row" key={task.id}>
                <div className="library-row-copy">
                  <strong>{projectTitles.get(task.project_id) ?? "Research project"}</strong>
                  <span>{new Date(task.created_at).toLocaleString()} · Task {task.id.slice(0, 8)}</span>
                </div>
                <span className={`task-status ${task.status}`}>{task.status.replace("_", " ")}</span>
                {task.safe_error_code && <small className="task-error-code">{task.safe_error_code}</small>}
                <button className="quiet-button library-open" onClick={() => onOpen(task)}>
                  Open <ArrowRight size={15} />
                </button>
              </article>
            ))}
          </div>
        </>
      )}
      {!tasksQuery.isLoading && !tasksQuery.isError && (tasksQuery.data?.total ?? 0) > 0 && (
        <nav className="library-pagination" aria-label="Research history pages">
          <button className="quiet-button" disabled={page === 0} onClick={() => setPage((current) => current - 1)}>Previous</button>
          <span>Page {page + 1} of {pageCount}</span>
          <button className="quiet-button" disabled={page + 1 >= pageCount} onClick={() => setPage((current) => current + 1)}>Next</button>
        </nav>
      )}
      {!tasksQuery.isLoading &&
        !tasksQuery.isError &&
        (tasksQuery.data?.total ?? 0) > 0 &&
        tasks.length === 0 && (
          <p className="empty-projects">No tasks match this search on the current page.</p>
        )}
    </section>
  );
}

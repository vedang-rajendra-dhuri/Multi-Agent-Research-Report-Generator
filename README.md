<<<<<<< HEAD
# ReportPilot

ReportPilot is a source-grounded research and report-generation workspace. It helps a user turn a research question into a structured report with linked source passages, claim assessments, a review process, and exportable output. The application combines a React frontend, a FastAPI backend, PostgreSQL persistence, a LangGraph research workflow, and a separate background worker.

## Overview

Research work often involves searching across many sources, organizing evidence, checking whether statements are supported, and turning findings into a report. These steps can be time-consuming and difficult to reproduce. A generated answer can also hide weak evidence, omit sources, or state uncertain conclusions too confidently.

ReportPilot addresses this by keeping research work in an owner-scoped project, persisting its tasks and evidence, attaching source records to report claims and sections, and requiring human review before a report is approved for export. The workflow is designed to make the research process inspectable; its AI-generated assessments are aids to review, not guarantees that a claim is true.

## Problem statement

- Research information is spread across websites and user-provided documents.
- A polished summary without traceable evidence is difficult to evaluate or trust.
- Research work can be lost when it is run synchronously or held only in a browser session.
- Reports need an explicit way for people to inspect citations, revise content, and decide whether it is ready to share.

## Objectives

1. Organize research briefs, supporting documents, tasks, and reports under user-owned projects.
2. Run bounded research workflows asynchronously and preserve task state and progress events.
3. Link findings and report sections to retrieved evidence, and record claim-level verification assessments.
4. Support human review, versioned revisions, and re-verification of revised reports.
5. Export approved reports in Markdown, DOCX, and PDF formats.
6. Provide a local development setup and a containerized deployment baseline.

## How it works

1. **Create an account and project.** A user registers or signs in, then creates a project to group related work.
2. **Prepare the research brief.** The brief includes a question, objectives, scope, desired depth, source preferences, optional recency, and output language.
3. **Add project documents (optional).** PDF, DOCX, TXT, and Markdown files are parsed into text, divided into bounded chunks, and stored with their project. PostgreSQL full-text search selects relevant passages for a task.
4. **Queue a research task.** The API validates ownership and creates a durable task. The frontend can follow its status and persisted events while the worker handles it.
5. **Plan and gather evidence.** A LangGraph workflow creates a bounded research plan, runs web searches through Tavily, and combines web results with any relevant project-document passages.
6. **Analyze and assess claims.** The workflow analyzes the supplied passages, associates findings with valid evidence IDs, assesses claims against the passages, and may perform a bounded supplementary search when important questions remain.
7. **Draft the report.** The report writer creates a structured report with citations limited to known source records and records limitations.
8. **Review and revise.** A person inspects the report and its sources, then approves, rejects, or submits a revision. Revised factual assertions are asynchronously re-verified and return to human review.
9. **Export.** Markdown, DOCX, and PDF exports are available only for approved reports.

```text
Browser
  └─ React + Vite frontend
       └─ FastAPI REST API ───── PostgreSQL
              ├─ Auth, projects, briefs, documents, reports
              ├─ Durable task queue and persisted events
              └─ Server-sent events for task progress
                       │
                 Research worker
                  ├─ LangGraph planner / researcher / analyst / verifier / writer
                  ├─ Tavily web search
                  ├─ OpenAI or Gemini language model
                  └─ PostgreSQL-backed LangGraph checkpointing
```

## Main components

### Frontend

The React and TypeScript application provides authentication, project and brief management, document upload, a paginated research library, live task status, report review, and export controls. Vite serves the frontend during development and builds static assets for the Nginx container.

The workspace analytics page provides interactive 7-, 30-, and 90-day views of research activity, task and report status, source totals, and recent tasks. Status filters narrow the recent-task list, and selecting a task opens its live workspace. Analytics are aggregated from the signed-in user's own projects and tasks; project totals include archived projects, while task, report, and source metrics use the selected calendar-day window in UTC.

### API

The FastAPI application exposes versioned endpoints under `/api/v1` for authentication, workspace analytics, projects, research briefs and tasks, documents, reports, review decisions, revisions, and exports. `GET /api/v1/analytics/workspace?days=30` returns owner-scoped workspace aggregates for 7, 30, or 90 calendar days. Interactive API documentation is available at `/docs` while the API is running. `/health/live` reports process liveness; `/health/ready` also checks PostgreSQL connectivity and migration status.

### Research worker and workflow

The worker claims queued tasks from PostgreSQL and runs the LangGraph workflow outside the HTTP request lifecycle. It persists stages and events, supports cancellation and recovery of interrupted work, and uses a PostgreSQL advisory lock to prevent multiple workers from consuming the same queue concurrently. LangGraph checkpoints are stored in PostgreSQL.

The workflow has five stages:

- **Planner:** creates research subquestions, search queries, scope boundaries, and a report outline.
- **Researcher:** retrieves search results and relevant project-document passages.
- **Analyst:** extracts findings, evidence links, open questions, and possible supplementary queries.
- **Verifier:** assesses each claim against its linked passage.
- **Writer:** drafts a structured report using the supplied findings and source records.

The number of research iterations, search results, and provider timeout are bounded by configuration.

### Persistence and documents

PostgreSQL stores users and sessions, projects and briefs, uploaded-document metadata and chunks, tasks and task events, sources and evidence passages, claims and assessments, report versions, and review decisions. Alembic manages schema migrations.

Document uploads are size and page limited. Text is extracted from supported formats and split into overlapping chunks. Retrieval currently uses English PostgreSQL full-text search, not vector embeddings. Uploaded content is private to its project; relevant passages may be sent to the configured model as research evidence.

### External providers

- **Language models:** OpenAI or Google Gemini, selected using `LLM_PROVIDER`.
- **Web search:** Tavily, selected using `SEARCH_PROVIDER`.

Provider credentials are read by the backend and worker; do not put them in frontend variables. Research execution requires both a configured supported language model and Tavily search. The application can start without provider keys, but research tasks cannot complete until they are configured.

## Technology

| Area | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod, Tailwind CSS |
| API | Python 3.11+, FastAPI, Pydantic, Uvicorn |
| Research orchestration | LangGraph, LangChain OpenAI and Google GenAI integrations |
| Search | Tavily Search API |
| Database | PostgreSQL 16, SQLAlchemy 2, psycopg, Alembic |
| Authentication | JWT access tokens, Argon2 password hashing, rotating refresh sessions in HttpOnly cookies, CSRF validation |
| Report/document processing | pypdf, python-docx, ReportLab, PostgreSQL full-text search |
| Containers | Docker Compose, PostgreSQL, Nginx |
| Tests | pytest, FastAPI test client, mocked external providers |

## Repository layout

```text
backend/
  app/
    agents/       LangGraph state and research workflow
    api/v1/       Authentication, project, document, research, report routes
    models/       SQLAlchemy persistence models
    providers/    Language-model and search integrations
    schemas/      API request and response schemas
    services/     Ingestion, retrieval, verification, rendering, exports
    workers/      Durable research-task worker
  alembic/        Database migrations
  tests/          Backend tests
frontend/
  src/
    api/          Frontend API client and types
    pages/        Analytics, research, library, workspace, and report screens
```

## Requirements

- Python 3.11 or newer.
- Node.js 22 or newer and npm.
- PostgreSQL (or Docker Desktop for the Compose setup).
- A random `SECRET_KEY` of at least 32 characters.
- To run research tasks: an OpenAI or Gemini API key and a Tavily API key.

## Configuration

Create a private root `.env` file from the example:

```powershell
Copy-Item .env.example .env
notepad .env
```

Generate a strong local secret and put the result in `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the provider values in `.env` to enable research:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-key
# Or use LLM_PROVIDER=gemini and GEMINI_API_KEY instead.
SEARCH_PROVIDER=tavily
SEARCH_PROVIDER_API_KEY=your-tavily-key
# Optional; defaults depend on the selected provider.
LLM_MODEL=
# Maximum time in seconds to wait for an LLM or search provider request (5-120).
PROVIDER_TIMEOUT_SECONDS=60
```

Keep `.env` private and never commit real credentials. `CORS_ORIGINS` must contain the exact browser origin(s), represented as a JSON array, for example `["http://localhost:5173"]`. In production, use HTTPS origins and secure database credentials.

## Run with Docker Compose

Docker Compose starts PostgreSQL, the API, the worker, and the frontend. From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose run --rm backend alembic upgrade head
docker compose up --build
```

The Compose configuration requires `SECRET_KEY`; edit `.env` before running the commands. By default, the database is named `researchpilot` and uses local-only example credentials. The database is not published to a host port, and its data persists in the `postgres_data` named volume.

Open:

- Frontend: `http://localhost:5173`
- API: `http://localhost:8000`
- Interactive API docs: `http://localhost:8000/docs`
- Liveness: `http://localhost:8000/health/live`
- Readiness: `http://localhost:8000/health/ready`

To stop the services, press `Ctrl+C` and run `docker compose down`. To also remove the local database volume and its data, run `docker compose down -v`.

If you change `POSTGRES_DB`, `POSTGRES_USER`, or `POSTGRES_PASSWORD`, ensure `DATABASE_URL` uses matching credentials and the Compose hostname `db`. Do not use the example database credentials outside local development.

### Troubleshooting: `failed to resolve host 'db'`

The hostname `db` is only available to containers on the Docker Compose network. If you start Uvicorn, Alembic, or the worker directly from Windows, they run outside that network and cannot resolve `db`. Choose one setup:

- **Run the whole application in Compose:** keep the Compose database URL using host `db`, apply migrations, then start the services:

  ```powershell
  docker compose run --rm backend alembic upgrade head
  docker compose up --build
  ```

- **Run the API and worker on Windows:** use a PostgreSQL server reachable from Windows and set `DATABASE_URL` in the root `.env` to that server's host, usually `localhost`, with the matching database, username, and password. Set `DATABASE_SSLMODE=disable` only for a local PostgreSQL server without TLS. The Compose database is not published to a host port by default, so `localhost:5432` will not reach that container.

Do not use a Windows-host URL such as `localhost` for the database connection inside the backend or worker containers; use `db` there.

## Run locally without Docker

This mode requires a PostgreSQL server running on the host. Configure `DATABASE_URL` in the root `.env` to use the host database (usually `localhost`) rather than the Compose-only `db` hostname. For a local server without TLS, set `DATABASE_SSLMODE=disable`. Configure `SECRET_KEY` and the model/search providers as described above.

Create and activate a Python environment, install dependencies, and apply migrations from the repository root:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m alembic -c backend\alembic.ini upgrade head
```

Run the API in that terminal:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

In a second PowerShell terminal, start the worker:

```powershell
Set-Location backend
..\.venv\Scripts\Activate.ps1
python -m app.workers.research
```

In a third terminal, install frontend dependencies and start Vite:

```powershell
npm --prefix frontend install
npm --prefix frontend run dev
```

The frontend is served at `http://localhost:5173` and the API at `http://localhost:8000`. The frontend API client defaults to `http://localhost:8000/api/v1`; set `VITE_API_BASE_URL` when building the frontend to use a different API URL.

## API capabilities

All application endpoints are under `/api/v1`. The main route groups are:

- `/auth`: registration, login, refresh, logout, and current-user information.
- `/projects`: create and manage owner-scoped projects and research briefs.
- `/projects/{project_id}/documents`: upload, list, and delete project documents.
- `/projects/{project_id}/briefs/{brief_id}/tasks` and `/tasks`: queue and inspect research tasks, cancel or resume tasks, and stream task events.
- `/reports`: inspect report versions, review or revise reports, and export approved reports as Markdown, DOCX, or PDF.

Use `/docs` for the live OpenAPI schema and exact request/response definitions.

## Tests and build

From the repository root, run the backend suite:

```powershell
python -m pytest -q
```

Build and type-check the frontend:

```powershell
npm --prefix frontend run build
```

Backend tests use mocked providers and do not require live model or search credentials. Validate database migrations and provider integration separately in a dedicated development environment before deployment.

### Troubleshooting: research task fails with `DeadlineExceeded`

The configured language-model or search provider did not respond before its request deadline. The default provider timeout is 60 seconds and can be set from 5 to 120 seconds using `PROVIDER_TIMEOUT_SECONDS`. If requests are taking longer, raise the value in `.env` (for example, to `90`) and recreate the backend and worker containers so both receive the updated setting:

```powershell
docker compose up -d --build --force-recreate backend worker
```

Then retry the failed research task in the workspace. If it continues to fail, check outbound internet access from Docker, provider availability and quotas, and that the configured API key and model are valid. Increasing the timeout will not fix invalid credentials, unavailable models, exhausted quotas, or blocked network access.

## Security and operational notes

- Project, document, task, and report access is scoped to the authenticated owner.
- Authentication uses Argon2 password hashes, short-lived access tokens, rotating refresh tokens, CSRF checks, and PostgreSQL-backed rate limits.
- Task creation supports idempotency; task progress can be replayed using persisted events and streamed using server-sent events.
- Uploaded documents and web search passages are untrusted input. The workflow is instructed not to treat passage content as control instructions, and it filters report citations to known source IDs.
- Claim verification is an AI-generated assessment, not proof of factual accuracy. Always inspect the original evidence and apply human judgment.
- Only approved reports can be exported.
- Use TLS, production-grade secrets and database credentials, backups, and monitoring when deploying. The bundled Compose credentials are for local development only.

## Current limitations

Workspace membership, password recovery, and broader settings screens are not implemented. Document retrieval uses English PostgreSQL full-text search rather than embedding-based semantic search. Search quality and generated report quality depend on the external providers. Live database and provider integration should be validated before production use; the project should not be treated as production-ready without additional deployment-specific security hardening and operational testing.
=======
# ResearchPilot
>>>>>>> f44f7f9a4ae108aaeb31489c975b67d5e6ca263d

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ReportPilot — Interactive Architecture & Workspace Guide</title>
    <!-- Tailwind CSS CDN for styling -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- FontAwesome for Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                        mono: ['JetBrains Mono', 'monospace'],
                    },
                }
            }
        }
    </script>
    <style>
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .code-block { font-family: 'JetBrains Mono', monospace; }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 font-sans antialiased selection:bg-indigo-500 selection:text-white">

    <!-- Top Navigation / Header Banner -->
    <header class="border-b border-slate-800 bg-slate-900/60 sticky top-0 z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                    <i class="fa-solid fa-compass-drafting text-white text-lg"></i>
                </div>
                <div>
                    <h1 class="font-bold text-lg tracking-tight text-white flex items-center gap-2">
                        ReportPilot <span class="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-400 font-normal border border-indigo-500/30">Interactive Docs</span>
                    </h1>
                </div>
            </div>
            <div class="flex items-center space-x-4 text-sm">
                <span class="hidden sm:inline-flex items-center gap-1.5 text-slate-400">
                    <span class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span> FastAPI + React + LangGraph
                </span>
                <button onclick="switchTab('quickstart')" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition shadow-sm">
                    Get Started <i class="fa-solid fa-arrow-right ml-1"></i>
                </button>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        <!-- Hero Section -->
        <div class="mb-10 text-center max-w-3xl mx-auto">
            <h2 class="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-4">
                Source-Grounded Research & Report Workspace
            </h2>
            <p class="text-slate-400 text-base sm:text-lg leading-relaxed">
                Turn complex research questions into structured reports with linked source passages, claim assessments, real-time event streaming, and rigorous human review workflows.
            </p>
        </div>

        <!-- Interactive Navigation Tabs -->
        <div class="flex flex-wrap justify-center gap-2 mb-8 border-b border-slate-800 pb-4">
            <button onclick="switchTab('overview')" id="btn-overview" class="tab-btn px-4 py-2 rounded-lg font-medium text-sm transition bg-indigo-600 text-white shadow-md">
                <i class="fa-solid fa-house-chimney mr-2"></i>Overview & Flow
            </button>
            <button onclick="switchTab('architecture')" id="btn-architecture" class="tab-btn px-4 py-2 rounded-lg font-medium text-sm transition bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800">
                <i class="fa-solid fa-network-wired mr-2"></i>System Architecture
            </button>
            <button onclick="switchTab('workflow')" id="btn-workflow" class="tab-btn px-4 py-2 rounded-lg font-medium text-sm transition bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800">
                <i class="fa-solid fa-diagram-project mr-2"></i>Workflow & Graph
            </button>
            <button onclick="switchTab('techstack')" id="btn-techstack" class="tab-btn px-4 py-2 rounded-lg font-medium text-sm transition bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800">
                <i class="fa-solid fa-layer-group mr-2"></i>Tech Stack
            </button>
            <button onclick="switchTab('quickstart')" id="btn-quickstart" class="tab-btn px-4 py-2 rounded-lg font-medium text-sm transition bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800">
                <i class="fa-solid fa-terminal mr-2"></i>Quickstart & Setup
            </button>
        </div>

        <!-- TAB 1: OVERVIEW & ARCHITECTURE MAP -->
        <div id="tab-overview" class="tab-content active space-y-8">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl">
                    <div class="h-12 w-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 text-xl">
                        <i class="fa-solid fa-folder-tree"></i>
                    </div>
                    <h3 class="text-lg font-semibold text-white mb-2">Owner-Scoped Projects</h3>
                    <p class="text-slate-400 text-sm leading-relaxed">
                        Organize briefs, supporting documents, tasks, and versioned reports securely inside dedicated projects owned by authenticated users.
                    </p>
                </div>
                <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl">
                    <div class="h-12 w-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center text-violet-400 mb-4 text-xl">
                        <i class="fa-solid fa-bolt"></i>
                    </div>
                    <h3 class="text-lg font-semibold text-white mb-2">Durable Asynchronous Queue</h3>
                    <p class="text-slate-400 text-sm leading-relaxed">
                        Background workers claim tasks via PostgreSQL row locks (`SKIP LOCKED`) and advisory locks, running LangGraph workflows outside HTTP limits.
                    </p>
                </div>
                <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-xl">
                    <div class="h-12 w-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4 text-xl">
                        <i class="fa-solid fa-shield-check"></i>
                    </div>
                    <h3 class="text-lg font-semibold text-white mb-2">Human Review & Verifications</h3>
                    <p class="text-slate-400 text-sm leading-relaxed">
                        Every claim is verified against linked passages. AI assessments act as aids to review, requiring human approval before markdown, DOCX, or PDF exports.
                    </p>
                </div>
            </div>

            <!-- Interactive System Flowchart Visual -->
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8">
                <h3 class="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                    <i class="fa-solid fa-route text-indigo-400"></i> End-to-End Execution Flow
                </h3>
                <div class="grid grid-cols-1 sm:grid-cols-5 gap-4 relative">
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 text-center">
                        <div class="text-indigo-400 font-mono text-xs mb-1">STEP 1</div>
                        <div class="font-semibold text-sm text-white mb-1">Brief & Ingestion</div>
                        <p class="text-slate-400 text-xs">User creates brief & uploads PDFs/docs into chunks.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 text-center">
                        <div class="text-indigo-400 font-mono text-xs mb-1">STEP 2</div>
                        <div class="font-semibold text-sm text-white mb-1">Task Queueing</div>
                        <p class="text-slate-400 text-xs">API validates ownership & creates durable task with idempotency.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 text-center">
                        <div class="text-indigo-400 font-mono text-xs mb-1">STEP 3</div>
                        <div class="font-semibold text-sm text-white mb-1">LangGraph Worker</div>
                        <p class="text-slate-400 text-xs">Worker executes planner, Tavily search, & analyst nodes.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 text-center">
                        <div class="text-indigo-400 font-mono text-xs mb-1">STEP 4</div>
                        <div class="font-semibold text-sm text-white mb-1">Verification</div>
                        <p class="text-slate-400 text-xs">Verifier checks claims against sources; unsupported claims dropped.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4 text-center">
                        <div class="text-indigo-400 font-mono text-xs mb-1">STEP 5</div>
                        <div class="font-semibold text-sm text-white mb-1">Review & Export</div>
                        <p class="text-slate-400 text-xs">Human inspects evidence, approves report, & exports DOCX/PDF.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 2: SYSTEM ARCHITECTURE -->
        <div id="tab-architecture" class="tab-content space-y-6">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8">
                <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <i class="fa-solid fa-server text-indigo-400"></i> Container & Component Architecture
                </h3>
                <p class="text-slate-400 text-sm mb-6">
                    ReportPilot is engineered as a decoupled client-server architecture running inside Docker Compose.
                </p>

                <div class="bg-slate-950 border border-slate-800 rounded-xl p-6 font-mono text-xs text-slate-300 overflow-x-auto leading-relaxed">
<pre>
Browser (React + Vite SPA)
  │  (HTTP REST / SSE Stream with Last-Event-ID)
  ▼
FastAPI REST API (/api/v1) ────── PostgreSQL 16
  ├─ Auth, projects, briefs, documents     ├─ Users, sessions, briefs
  ├─ Task queueing & idempotency           ├─ Documents & text chunks
  └─ Server-Sent Events (SSE) stream       ├─ Tasks, events & checkpoints
                                           └─ Sources, claims, report versions
  ▲
  │ (Claims tasks via FOR UPDATE SKIP LOCKED & advisory locks)
Research Worker
  ├─ LangGraph Workflow (Planner, Researcher, Analyst, Verifier, Writer)
  ├─ Tavily Web Search API
  └─ OpenAI or Google Gemini LLM
</pre>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                    <h4 class="text-base font-semibold text-white mb-3 flex items-center gap-2">
                        <i class="fa-solid fa-database text-indigo-400"></i> Persistence & Storage
                    </h4>
                    <ul class="space-y-2 text-sm text-slate-400">
                        <li><strong class="text-white">PostgreSQL 16:</strong> Single source of truth for durable application state and LangGraph checkpoints.</li>
                        <li><strong class="text-white">Full-Text Search:</strong> Uses built-in English PostgreSQL FTS for document retrieval without external vector DB dependencies.</li>
                        <li><strong class="text-white">Alembic:</strong> Structured database schema migrations.</li>
                    </ul>
                </div>
                <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6">
                    <h4 class="text-base font-semibold text-white mb-3 flex items-center gap-2">
                        <i class="fa-solid fa-lock text-indigo-400"></i> Security & Auth
                    </h4>
                    <ul class="space-y-2 text-sm text-slate-400">
                        <li><strong class="text-white">Argon2:</strong> Secure password hashing.</li>
                        <li><strong class="text-white">Tokens & Cookies:</strong> Short-lived access tokens with rotating refresh sessions in HttpOnly cookies.</li>
                        <li><strong class="text-white">CSRF Protection:</strong> Cookie-derived header validation on unsafe requests.</li>
                    </ul>
                </div>
            </div>
        </div>

        <!-- TAB 3: WORKFLOW & GRAPH -->
        <div id="tab-workflow" class="tab-content space-y-6">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8">
                <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <i class="fa-solid fa-diagram-project text-indigo-400"></i> LangGraph 5-Stage Research Workflow
                </h3>
                <p class="text-slate-400 text-sm mb-6">
                    The research worker executes a bounded state machine managed by LangGraph. All stages persist checkpoints in PostgreSQL to allow seamless recovery from interruptions.
                </p>

                <div class="grid grid-cols-1 sm:grid-cols-5 gap-4">
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4">
                        <div class="text-indigo-400 font-bold mb-1">1. Planner</div>
                        <p class="text-xs text-slate-400">Creates research subquestions, search queries, scope boundaries, and outline.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4">
                        <div class="text-indigo-400 font-bold mb-1">2. Researcher</div>
                        <p class="text-xs text-slate-400">Retrieves web search results via Tavily and relevant project-document passages.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4">
                        <div class="text-indigo-400 font-bold mb-1">3. Analyst</div>
                        <p class="text-xs text-slate-400">Extracts findings, evidence links, open questions, and supplementary queries.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4">
                        <div class="text-indigo-400 font-bold mb-1">4. Verifier</div>
                        <p class="text-xs text-slate-400">Assesses each claim against linked passage. Unsupported claims are dropped.</p>
                    </div>
                    <div class="bg-slate-950 border border-slate-800 rounded-xl p-4">
                        <div class="text-indigo-400 font-bold mb-1">5. Writer</div>
                        <p class="text-xs text-slate-400">Drafts structured report with verified citations limited to known source records.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- TAB 4: TECH STACK -->
        <div id="tab-techstack" class="tab-content space-y-6">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8">
                <h3 class="text-xl font-bold text-white mb-6 flex items-center gap-2">
                    <i class="fa-solid fa-layer-group text-indigo-400"></i> Technology Matrix
                </h3>
                
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-slate-300">
                        <thead class="bg-slate-950 text-slate-400 uppercase text-xs tracking-wider border-b border-slate-800">
                            <tr>
                                <th class="py-3 px-4">Area</th>
                                <th class="py-3 px-4">Technology</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-800">
                            <tr>
                                <td class="py-3 px-4 font-semibold text-white">Frontend</td>
                                <td class="py-3 px-4 text-slate-400">React 18, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod, Tailwind CSS</td>
                            </tr>
                            <tr>
                                <td class="py-3 px-4 font-semibold text-white">API</td>
                                <td class="py-3 px-4 text-slate-400">Python 3.11+, FastAPI, Pydantic, Uvicorn</td>
                            </tr>
                            <tr>
                                <td class="py-3 px-4 font-semibold text-white">Research Orchestration</td>
                                <td class="py-3 px-4 text-slate-400">LangGraph, LangChain OpenAI and Google GenAI integrations</td>
                            </tr>
                            <tr>
                                <td class="py-3 px-4 font-semibold text-white">Search & Models</td>
                                <td class="py-3 px-4 text-slate-400">Tavily Search API, OpenAI / Google Gemini</td>
                            </tr>
                            <tr>
                                <td class="py-3 px-4 font-semibold text-white">Database</td>
                                <td class="py-3 px-4 text-slate-400">PostgreSQL 16, SQLAlchemy 2, psycopg, Alembic</td>
                            </tr>
                            <tr>
                                <td class="py-3 px-4 font-semibold text-white">Document Processing</td>
                                <td class="py-3 px-4 text-slate-400">pypdf, python-docx, ReportLab, PostgreSQL full-text search</td>
                            </tr>
                            <tr>
                                <td class="py-3 px-4 font-semibold text-white">Containers & Testing</td>
                                <td class="py-3 px-4 text-slate-400">Docker Compose, Nginx, pytest, FastAPI test client</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- TAB 5: QUICKSTART & SETUP -->
        <div id="tab-quickstart" class="tab-content space-y-6">
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8">
                <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <i class="fa-solid fa-terminal text-indigo-400"></i> Quickstart with Docker Compose
                </h3>
                <p class="text-slate-400 text-sm mb-4">
                    Run PostgreSQL, backend API, background worker, and Vite/Nginx frontend instantly using Docker Compose.
                </p>

                <div class="space-y-4">
                    <div>
                        <div class="text-xs font-mono text-indigo-400 mb-1">1. Copy environment template</div>
                        <div class="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-sm text-emerald-400 flex items-center justify-between">
                            <span>Copy-Item .env.example .env</span>
                            <button onclick="navigator.clipboard.writeText('Copy-Item .env.example .env')" class="text-slate-400 hover:text-white text-xs"><i class="fa-solid fa-copy"></i></button>
                        </div>
                    </div>
                    <div>
                        <div class="text-xs font-mono text-indigo-400 mb-1">2. Run database migrations & start containers</div>
                        <div class="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-sm text-emerald-400 flex items-center justify-between">
                            <span>docker compose run --rm backend alembic upgrade head<br>docker compose up --build</span>
                            <button onclick="navigator.clipboard.writeText('docker compose run --rm backend alembic upgrade head\ndocker compose up --build')" class="text-slate-400 hover:text-white text-xs"><i class="fa-solid fa-copy"></i></button>
                        </div>
                    </div>
                </div>

                <div class="mt-6 pt-6 border-t border-slate-800 grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                    <a href="http://localhost:5173" target="_blank" class="p-3 bg-slate-950 border border-slate-800 rounded-xl hover:border-indigo-500 transition block">
                        <div class="text-xs text-slate-400">Frontend App</div>
                        <div class="font-mono text-sm text-indigo-400 font-semibold">localhost:5173</div>
                    </a>
                    <a href="http://localhost:8000/docs" target="_blank" class="p-3 bg-slate-950 border border-slate-800 rounded-xl hover:border-indigo-500 transition block">
                        <div class="text-xs text-slate-400">Interactive API Docs</div>
                        <div class="font-mono text-sm text-indigo-400 font-semibold">localhost:8000/docs</div>
                    </a>
                    <a href="http://localhost:8000/health/live" target="_blank" class="p-3 bg-slate-950 border border-slate-800 rounded-xl hover:border-indigo-500 transition block">
                        <div class="text-xs text-slate-400">Liveness Probe</div>
                        <div class="font-mono text-sm text-emerald-400 font-semibold">/health/live</div>
                    </a>
                    <a href="http://localhost:8000/health/ready" target="_blank" class="p-3 bg-slate-950 border border-slate-800 rounded-xl hover:border-indigo-500 transition block">
                        <div class="text-xs text-slate-400">Readiness Probe</div>
                        <div class="font-mono text-sm text-emerald-400 font-semibold">/health/ready</div>
                    </a>
                </div>
            </div>
        </div>

    </main>

    <!-- Footer -->
    <footer class="border-t border-slate-800 mt-16 py-6 text-center text-slate-500 text-sm">
        <p>ReportPilot &bull; Source-Grounded Research Workspace &bull; Powered by FastAPI & LangGraph</p>
    </footer>

    <!-- Interactive Tab Script -->
    <script>
        function switchTab(tabId) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(el => {
                el.classList.remove('active');
            });
            // Remove active styles from all buttons
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('bg-indigo-600', 'text-white', 'shadow-md');
                btn.classList.add('bg-slate-900', 'text-slate-400');
            });
            // Show target tab
            document.getElementById('tab-' + tabId).classList.add('active');
            // Highlight active button
            const activeBtn = document.getElementById('btn-' + tabId);
            activeBtn.classList.remove('bg-slate-900', 'text-slate-400');
            activeBtn.classList.add('bg-indigo-600', 'text-white', 'shadow-md');
        }
    </script>
</body>
</html>

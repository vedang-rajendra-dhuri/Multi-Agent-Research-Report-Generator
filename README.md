<div align="center">

# 🧭 ResearchPilot

<p align="center">
  <b>Source-Grounded Research & Report-Generation Workspace</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/LangGraph-Workflow-333333?style=flat-square&logo=chainlink&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
</p>

</div>

---

## 🚀 Overview

**ResearchPilot** is a source-grounded research and report-generation workspace. It helps a user turn a research question into a structured report with linked source passages, claim assessments, a review process, and exportable output. The application combines a React frontend, a FastAPI backend, PostgreSQL persistence, a LangGraph research workflow, and a separate background worker.

Research information is often scattered across websites and PDFs without traceable evidence. ResearchPilot addresses this by keeping research work in an owner-scoped project, persisting its tasks and evidence, attaching source records to report claims and sections, and requiring human review before a report is approved for export.

---

## 🏗️ Runtime System Architecture

```text
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

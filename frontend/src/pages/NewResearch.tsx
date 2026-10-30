import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, CircleAlert, LoaderCircle } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { documentsApi, researchApi, type Project, type ResearchTask } from "../api/client";

const formSchema = z.object({
  project_id: z.string().min(1, "Choose a project."),
  research_question: z
    .string()
    .trim()
    .min(10, "Describe your research question in at least 10 characters.")
    .max(5000),
  objectives: z.string().max(5000),
  scope: z.string().max(10_000),
  depth: z.enum(["quick", "standard", "deep"]),
  source_preferences: z.string().max(2000),
  recency_days: z.string(),
  output_format: z.literal("markdown"),
  output_language: z.string().min(2).max(80),
});

type FormValues = z.infer<typeof formSchema>;

interface NewResearchProps {
  projects: Project[];
  initialProjectId?: string;
  onStarted: (task: ResearchTask) => void;
  onCancel: () => void;
}

export default function NewResearch({
  projects,
  initialProjectId,
  onStarted,
  onCancel,
}: NewResearchProps) {
  const [serverError, setServerError] = useState("");
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      project_id: projects[0]?.id ?? "",
      objectives: "",
      scope: "",
      depth: "standard",
      source_preferences: "",
      recency_days: "",
      output_format: "markdown",
      output_language: "en",
    },
  });
  const activeProjectId = watch("project_id");
  const documentsQuery = useQuery({
    queryKey: ["documents", activeProjectId],
    queryFn: () => documentsApi.list(activeProjectId),
    enabled: Boolean(activeProjectId),
  });
  const uploadDocument = useMutation({
    mutationFn: (file: File) => documentsApi.upload(activeProjectId, file),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents", activeProjectId] });
    },
  });
  const removeDocument = useMutation({
    mutationFn: (documentId: string) => documentsApi.remove(activeProjectId, documentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents", activeProjectId] });
    },
  });

  useEffect(() => {
    if (
      initialProjectId &&
      projects.some((project) => project.id === initialProjectId)
    ) {
      setValue("project_id", initialProjectId);
    }
  }, [initialProjectId, projects, setValue]);

  async function submit(values: FormValues) {
    setServerError("");
    try {
      const recencyDays = values.recency_days.trim()
        ? Number(values.recency_days)
        : undefined;
      if (
        recencyDays !== undefined &&
        (!Number.isInteger(recencyDays) || recencyDays < 1 || recencyDays > 36_500)
      ) {
        setServerError("Recency must be a whole number between 1 and 36,500 days.");
        return;
      }
      const brief = await researchApi.createBrief(values.project_id, {
        research_question: values.research_question,
        objectives: values.objectives.split("\n").map((item) => item.trim()).filter(Boolean),
        scope: values.scope.trim() || undefined,
        depth: values.depth,
        source_preferences: values.source_preferences
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        recency_days: recencyDays,
        output_format: values.output_format,
        output_language: values.output_language.trim(),
      });
      const task = await researchApi.start(
        values.project_id,
        brief.id,
        crypto.randomUUID(),
      );
      onStarted(task);
    } catch (reason) {
      setServerError(
        reason instanceof Error ? reason.message : "Unable to start the research task.",
      );
    }
  }

  return (
    <section className="research-form-card">
      <button className="back-button" onClick={onCancel} type="button">
        <ArrowLeft size={16} /> Back to projects
      </button>
      <p className="eyebrow">RESEARCH BRIEF</p>
      <h2>Start evidence-based research</h2>
      <p className="form-intro">
        Your brief is saved before the task is queued. Results will be based on configured
        providers and need human review.
      </p>
      {serverError && (
        <div className="alert" role="alert">
          <CircleAlert size={18} />
          {serverError}
        </div>
      )}
      {projects.length === 0 ? (
        <div className="empty-projects">
          Create a project before starting research.
          <button className="text-button" onClick={onCancel}>Return to projects</button>
        </div>
      ) : (
        <form className="research-form" onSubmit={handleSubmit(submit)}>
          <label>
            Project
            <select {...register("project_id")}>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.title}
                </option>
              ))}
            </select>
            {errors.project_id && <small className="field-error">{errors.project_id.message}</small>}
          </label>
          <section className="project-documents">
            <div className="project-documents-heading">
              <div>
                <strong>Project source documents</strong>
                <span>PDF, DOCX, TXT, or Markdown · up to 10 MB per file</span>
              </div>
              <label className="document-upload-button">
                {uploadDocument.isPending ? <LoaderCircle className="spin" size={15} /> : null}
                Add document
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
                  disabled={!activeProjectId || uploadDocument.isPending}
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    if (file) uploadDocument.mutate(file);
                    event.currentTarget.value = "";
                  }}
                />
              </label>
            </div>
            <p className="document-disclosure">Uploaded text is stored in this project and may be sent to your configured research model as evidence when you queue a task.</p>
            {documentsQuery.isLoading && <p className="document-empty">Loading project documents…</p>}
            {documentsQuery.isError && <div className="alert" role="alert"><CircleAlert size={16} />Unable to load documents: {documentsQuery.error.message}</div>}
            {uploadDocument.isError && <div className="alert" role="alert"><CircleAlert size={16} />Upload failed: {uploadDocument.error.message}</div>}
            {removeDocument.isError && <div className="alert" role="alert"><CircleAlert size={16} />Unable to remove document: {removeDocument.error.message}</div>}
            {!documentsQuery.isLoading && !documentsQuery.isError && documentsQuery.data?.length === 0 && (
              <p className="document-empty">No source documents uploaded for this project.</p>
            )}
            {documentsQuery.data?.map((document) => (
              <article className="document-row" key={document.id}>
                <div><strong>{document.file_name}</strong><span>{document.chunk_count} indexed sections · {(document.size_bytes / 1024).toFixed(0)} KB</span></div>
                <button
                  className="quiet-button"
                  type="button"
                  disabled={removeDocument.isPending}
                  onClick={() => {
                    if (window.confirm(`Remove "${document.file_name}" from this project?`)) {
                      removeDocument.mutate(document.id);
                    }
                  }}
                >
                  Remove
                </button>
              </article>
            ))}
          </section>
          <label>
            Research question
            <textarea
              {...register("research_question")}
              rows={3}
              placeholder="What specific question should the research answer?"
            />
            {errors.research_question && <small className="field-error">{errors.research_question.message}</small>}
          </label>
          <label>
            Objectives <span className="label-hint">One objective per line</span>
            <textarea {...register("objectives")} rows={2} placeholder="Compare options&#10;Identify evidence gaps" />
          </label>
          <label>
            Scope <span className="label-hint">Optional boundaries or context</span>
            <textarea {...register("scope")} rows={2} placeholder="Geography, audience, exclusions…" />
          </label>
          <div className="form-grid">
            <label>
              Research depth
              <select {...register("depth")}>
                <option value="quick">Quick</option>
                <option value="standard">Standard</option>
                <option value="deep">Deep</option>
              </select>
            </label>
            <label>
              Only sources from the last N days
              <input {...register("recency_days")} type="number" min={1} max={36500} placeholder="Any date" />
            </label>
          </div>
          <label>
            Source preferences <span className="label-hint">One preference per line</span>
            <textarea {...register("source_preferences")} rows={2} placeholder="Academic sources&#10;Government publications" />
          </label>
          <div className="form-grid">
            <label>
              Output format
              <select {...register("output_format")}>
                <option value="markdown">Markdown</option>
              </select>
            </label>
            <label>
              Output language
              <input {...register("output_language")} maxLength={80} />
            </label>
          </div>
          <button className="primary-button submit-research" type="submit" disabled={isSubmitting}>
            {isSubmitting ? <LoaderCircle className="spin" size={17} /> : null}
            Queue research
            <ArrowRight size={17} />
          </button>
        </form>
      )}
    </section>
  );
}

import { useEffect, useState, type FormEvent } from "react";
import { Check, CircleAlert, Download, FileText, Pencil, Save, ShieldCheck, X, XCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { ReportDetail, ReportRevision } from "../api/client";

interface ReportEditorProps {
  report: ReportDetail;
  busy: boolean;
  error: string;
  onReview: (decision: "approved" | "rejected", comment?: string) => void;
  onExport: (format: "markdown" | "pdf" | "docx") => void;
  onRevise: (revision: ReportRevision) => Promise<boolean>;
  onReverify: () => void;
}

export default function ReportEditor({
  report,
  busy,
  error,
  onReview,
  onExport,
  onRevise,
  onReverify,
}: ReportEditorProps) {
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [comment, setComment] = useState("");
  const [editing, setEditing] = useState(false);
  const [executiveSummary, setExecutiveSummary] = useState(report.version.executive_summary);
  const [sections, setSections] = useState(report.version.sections);
  const [methodology, setMethodology] = useState(report.version.methodology);
  const [limitations, setLimitations] = useState(report.version.limitations.join("\n"));
  const [revisionError, setRevisionError] = useState("");

  useEffect(() => {
    setExecutiveSummary(report.version.executive_summary);
    setSections(report.version.sections);
    setMethodology(report.version.methodology);
    setLimitations(report.version.limitations.join("\n"));
    setEditing(false);
    setRevisionError("");
  }, [report.version.id]);

  const factualClaims = report.claims.filter((claim) => claim.claim_type === "factual");
  const linkedClaims = factualClaims.filter((claim) => claim.evidence.length > 0).length;
  const checkedClaims = factualClaims.filter((claim) =>
    claim.verifications.some(
      (verification) =>
        verification.status !== "not_checked" &&
        verification.status !== "source_unavailable",
    ),
  ).length;
  const citationMarkdown = report.version.markdown.replace(
    /\[([a-z0-9-]{1,64})\]/gi,
    (citation, sourceId: string) =>
      report.sources.some((source) => source.provider_source_id === sourceId)
        ? `[${citation}](#source:${sourceId})`
        : citation,
  );
  const selectedSource = report.sources.find(
    (source) => source.provider_source_id === selectedSourceId,
  );

  async function submitRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRevisionError("");
    const saved = await onRevise({
      base_version: report.current_version,
      executive_summary: executiveSummary.trim(),
      sections: sections.map((section) => ({
        ...section,
        title: section.title.trim(),
        content: section.content.trim(),
      })),
      methodology: methodology.trim(),
      limitations: limitations.split("\n").map((item) => item.trim()).filter(Boolean),
      source_ids: report.version.sections
        .flatMap((section) => section.source_ids)
        .concat(
          report.sources
            .filter((source) => report.version.markdown.includes(`[${source.provider_source_id}]`))
            .map((source) => source.provider_source_id),
        )
        .filter((id, index, ids) => ids.indexOf(id) === index),
    });
    if (saved) {
      setEditing(false);
    } else {
      setRevisionError("The revision was not saved. Check the error above and try again.");
    }
  }

  return (
    <section className="report-review">
      <header className="report-toolbar">
        <div className="report-title">
          <FileText size={18} />
          <div>
            <strong>Report review</strong>
            <span>Version {report.version.version} · {report.review_status.replace("_", " ")} · Verification {report.version.verification_status}</span>
          </div>
        </div>
        {report.review_status === "approved" && (
          <div className="export-actions">
            <button className="quiet-button export-button" onClick={() => onExport("markdown")} disabled={busy}>
              <Download size={15} /> Markdown
            </button>
            <button className="quiet-button export-button" onClick={() => onExport("docx")} disabled={busy}>
              <Download size={15} /> DOCX
            </button>
            <button className="quiet-button export-button" onClick={() => onExport("pdf")} disabled={busy}>
              <Download size={15} /> PDF
            </button>
          </div>
        )}
        {report.review_status !== "pending" && !editing && (
          <button className="quiet-button export-button" onClick={() => setEditing(true)} disabled={busy}>
            <Pencil size={15} /> Revise report
          </button>
        )}
      </header>

      <div className="coverage-row">
        <div><strong>{factualClaims.length ? Math.round((linkedClaims / factualClaims.length) * 100) : 0}%</strong><span>original research claims linked to evidence</span></div>
        <div><strong>{factualClaims.length ? Math.round((checkedClaims / factualClaims.length) * 100) : 0}%</strong><span>original claims with a verification assessment</span></div>
        <p>Coverage describes stored claim/evidence records, not report accuracy. Revised versions show separate findings.</p>
      </div>
      {report.version.verification_status !== "completed" && (
        <div className={`revision-notice verification-${report.version.verification_status}`} role="status">
          {report.version.verification_status === "pending" && "This revision is queued for evidence verification. Review actions will be enabled when verification finishes."}
          {report.version.verification_status === "running" && "The worker is checking revised factual assertions against the task's evidence. Review actions will be enabled when verification finishes."}
          {report.version.verification_status === "failed" && (
            <>
              Verification failed. Retry before approving or rejecting this revision.
              <button className="quiet-button" onClick={onReverify} disabled={busy}>Retry verification</button>
            </>
          )}
        </div>
      )}

      <div className="report-layout">
        <article className="report-body">
          {report.version.version > 1 && (
            <div className="revision-notice" role="note">
              This version was edited after generation. Revision-specific assessments appear below; the original claim ledger still describes the initial research findings.
            </div>
          )}
          {editing ? (
            <form className="report-revision-form" onSubmit={submitRevision}>
              <h3>Revise version {report.current_version}</h3>
              <p>Saving creates a new version and sends it back for review. Citations are preserved; edited statements are not automatically re-verified.</p>
              <label>
                Executive summary
                <textarea required maxLength={10000} rows={5} value={executiveSummary} onChange={(event) => setExecutiveSummary(event.target.value)} />
              </label>
              {sections.map((section, index) => (
                <fieldset key={`${report.version.id}-${index}`}>
                  <legend>Section {index + 1}</legend>
                  <label>
                    Title
                    <input required maxLength={200} value={section.title} onChange={(event) => setSections((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item))} />
                  </label>
                  <label>
                    Content
                    <textarea required maxLength={20000} rows={6} value={section.content} onChange={(event) => setSections((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, content: event.target.value } : item))} />
                  </label>
                  <small>Sources: {section.source_ids.length ? section.source_ids.join(", ") : "None attached"}</small>
                </fieldset>
              ))}
              <label>
                Methodology
                <textarea required maxLength={5000} rows={4} value={methodology} onChange={(event) => setMethodology(event.target.value)} />
              </label>
              <label>
                Limitations <span className="label-hint">One limitation per line</span>
                <textarea maxLength={5000} rows={3} value={limitations} onChange={(event) => setLimitations(event.target.value)} />
              </label>
              {(error || revisionError) && <div className="alert" role="alert"><CircleAlert size={18} />{error || revisionError}</div>}
              <div className="review-buttons">
                <button className="reject-button" type="button" disabled={busy} onClick={() => setEditing(false)}><X size={15} /> Cancel</button>
                <button className="approve-button" type="submit" disabled={busy}><Save size={15} /> Save new version</button>
              </div>
            </form>
          ) : (
          <>
          <ReactMarkdown
            components={{
              a: ({ href, children }) =>
                href?.startsWith("#source:") ? (
                  <button
                    className="citation-link"
                    onClick={() => setSelectedSourceId(href.slice("#source:".length))}
                  >
                    {children}
                  </button>
                ) : (
                  <a href={href} target="_blank" rel="noreferrer">{children}</a>
                ),
            }}
          >
            {citationMarkdown}
          </ReactMarkdown>
          {report.review_status === "pending" && (
            <div className="review-actions">
              {report.version.verification_status === "completed" && report.version.version > 1 && (
                <section className="revision-verification-results">
                  <h3>Revision verification findings</h3>
                  {report.version.verification_results.map((finding, index) => (
                    <article key={`${finding.claim_id ?? finding.text ?? "finding"}-${index}`}>
                      <span className={`verification-status ${finding.status ?? "unsupported"}`}>{finding.status ?? "assessment unavailable"}</span>
                      {finding.text && <p>{finding.text}</p>}
                      <small>{finding.explanation}</small>
                    </article>
                  ))}
                  {report.version.verification_results.length === 0 && (
                    <p className="source-empty">No factual assertions were returned for this revision.</p>
                  )}
                </section>
              )}
              <label>
                Review note <span className="label-hint">Required when rejecting</span>
                <textarea
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  rows={3}
                  maxLength={5000}
                  placeholder="Optional approval note or reason for rejection"
                />
              </label>
              <div className="review-buttons">
                <button
                  className="reject-button"
                  disabled={busy || !comment.trim() || report.version.verification_status !== "completed"}
                  onClick={() => onReview("rejected", comment.trim())}
                >
                  <XCircle size={16} /> Reject draft
                </button>
                <button
                  className="approve-button"
                  disabled={busy || report.version.verification_status !== "completed"}
                  onClick={() => onReview("approved", comment.trim() || undefined)}
                >
                  <Check size={16} /> Approve report
                </button>
              </div>
            </div>
          )}
          {report.review_status === "approved" && (
            <div className="review-complete"><ShieldCheck size={17} /> This report version was approved.</div>
          )}
          {report.review_status === "rejected" && (
            <div className="review-rejected"><CircleAlert size={17} /> This report version was rejected. Revise it to submit a new version for review.</div>
          )}
          {error && <div className="alert" role="alert"><CircleAlert size={18} />{error}</div>}
          </>
          )}
        </article>
        <aside className="source-drawer">
          <h3>Sources & evidence</h3>
          {selectedSource ? (
            <div className="source-detail">
              <button className="text-button source-back" onClick={() => setSelectedSourceId(null)}>All sources</button>
              <h4>{selectedSource.title}</h4>
              {selectedSource.url.startsWith("document://") ? (
                <p className="document-source-label">Uploaded project document · {selectedSource.passages[0]?.locator ?? "Section location unavailable"}</p>
              ) : (
                <a href={selectedSource.url} target="_blank" rel="noreferrer">Open original source</a>
              )}
              <p>{selectedSource.publisher ?? "Publisher not provided"}{selectedSource.published_date ? ` · ${selectedSource.published_date}` : ""}</p>
              <p className="retrieved-label">Retrieved {new Date(selectedSource.created_at).toLocaleString()}</p>
              {selectedSource.passages.map((passage) => <blockquote key={passage.id}>{passage.text}</blockquote>)}
            </div>
          ) : (
            <ul className="source-list">
              {report.sources.map((source) => (
                <li key={source.id}>
                  <button onClick={() => setSelectedSourceId(source.provider_source_id)}>
                    <strong>{source.title}</strong>
                    <span>{source.publisher ?? "Publisher not provided"}</span>
                    <small>{source.passages.length} evidence passage{source.passages.length === 1 ? "" : "s"}</small>
                  </button>
                </li>
              ))}
              {report.sources.length === 0 && <li className="source-empty">No source records were retrieved for this report.</li>}
            </ul>
          )}
        </aside>
      </div>

      <section className="claim-review">
        <h3>Claim verification</h3>
        {report.claims.map((claim) => {
          const verification = claim.verifications[claim.verifications.length - 1];
          return (
            <article key={claim.id}>
              <div><strong>{claim.claim_type}</strong><span className={`verification-status ${verification?.status ?? "not_checked"}`}>{verification?.status ?? "not checked"}</span></div>
              <p>{claim.text}</p>
              <small>{claim.evidence.length} linked evidence passage{claim.evidence.length === 1 ? "" : "s"}</small>
              {verification && <p className="verification-note">{verification.explanation}</p>}
            </article>
          );
        })}
        {report.claims.length === 0 && <p className="source-empty">The workflow did not persist any structured factual claims.</p>}
      </section>
    </section>
  );
}

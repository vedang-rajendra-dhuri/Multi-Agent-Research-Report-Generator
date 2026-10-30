from app.agents.state import ResearchReport
from app.models.research import ResearchSource


def render_report_markdown(
    report: ResearchReport,
    sources: dict[str, ResearchSource],
) -> str:
    lines = ["# Research report", "", "## Executive summary", "", report.executive_summary]
    for section in report.sections:
        lines.extend(["", f"## {section.title}", "", section.content])
        citation_ids = [source_id for source_id in section.source_ids if source_id in sources]
        if citation_ids:
            lines.extend(["", "Sources: " + ", ".join(f"[{source_id}]" for source_id in citation_ids)])
    lines.extend(["", "## Methodology", "", report.methodology])
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in report.limitations)
    lines.extend(["", "## References"])
    for source_id in report.source_ids:
        source = sources.get(source_id)
        if source is not None:
            lines.append(f"- [{source_id}] {source.title} — {source.url}")
    return "\n".join(lines).strip() + "\n"

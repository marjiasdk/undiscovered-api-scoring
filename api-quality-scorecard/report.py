"""
Report generator for the OpenAPI scorecard.

Features:
- Computes overall + per-category scores (already in results)
- Lists specific issues
- Provides basic recommendations based on issue patterns
- Renders as text, markdown, or JSON
"""

from typing import Dict, Any, List
import json
import re


# --- Recommendation engine (basic, pattern-based) ----------------------------

PATTERNS = [
    # Documentation quality fixes
    (
        re.compile(r"Operation .* missing description", re.I),
        "Add a concise 'summary' and a clear 'description' to the operation.",
    ),
    (
        re.compile(r"Parameter '(.+?)'.*missing description", re.I),
        "Document the parameter with 'description', valid ranges, and examples.",
    ),
    (
        re.compile(r"Response \d{3} .* missing description", re.I),
        "Add a human-friendly 'description' to the response explaining when it occurs.",
    ),
    # Schema completeness fixes
    (
        re.compile(r"missing request body schema", re.I),
        "Under 'requestBody.content.<mimeType>.schema', reference or define a schema.",
    ),
    (
        re.compile(r"Response \d{3} .* missing schema", re.I),
        "Provide a schema under 'responses.<code>.content.<mimeType>.schema'.",
    ),
    (
        re.compile(r"Parameter '(.+?)'.* missing type", re.I),
        "Specify a JSON Schema type in the parameter's 'schema' (e.g., type: string).",
    ),
    (
        re.compile(r"Schema '(.+?)' missing required fields or properties", re.I),
        "Define 'properties' for the schema and a 'required' array listing mandatory fields.",
    ),
]


def _recommendation_for_issue(issue: str) -> str:
    for rx, rec in PATTERNS:
        if rx.search(issue):
            return rec
    # Fallback
    return "Clarify documentation and ensure all request/response bodies and parameters have complete schemas."


# --- Render helpers -----------------------------------------------------------


def _sorted_issues(issues: List[str]) -> List[str]:
    # deterministic order
    return sorted(set(issues), key=str.lower)


def _collect_recommendations(issues: List[str]) -> List[str]:
    recs = [_recommendation_for_issue(i) for i in issues]
    # deduplicate while preserving order
    seen = set()
    out = []
    for r in recs:
        if r not in seen:
            out.append(r)
            seen.add(r)
    return out


# --- Public API ---------------------------------------------------------------


def render_text(results: Dict[str, Any]) -> str:
    """
    Render a simple plaintext report.
    """
    doc = results.get("documentation_quality", {})
    sch = results.get("schema_completeness", {})
    overall = results.get("overall_score", 0)

    issues = _sorted_issues((doc.get("issues") or []) + (sch.get("issues") or []))
    recs = _collect_recommendations(issues)

    lines = []
    lines.append("OpenAPI Quality Report")
    lines.append("=" * 24)
    lines.append(f"Overall Score: {overall}/100")
    lines.append("")
    lines.append("Category Scores")
    lines.append("- Documentation Quality: " + str(doc.get("score", 0)))
    lines.append("- Schema Completeness : " + str(sch.get("score", 0)))
    lines.append("")
    lines.append("Issues")
    if issues:
        for i in issues:
            lines.append(f"  • {i}")
    else:
        lines.append("  • No issues found 🎉")
    lines.append("")
    lines.append("Recommendations")
    if recs:
        for r in recs:
            lines.append(f"  • {r}")
    else:
        lines.append("  • None — great job!")
    return "\n".join(lines)


def render_markdown(results: Dict[str, Any]) -> str:
    """
    Render a Markdown report (good for README/PR comments).
    """
    doc = results.get("documentation_quality", {})
    sch = results.get("schema_completeness", {})
    overall = results.get("overall_score", 0)

    issues = _sorted_issues((doc.get("issues") or []) + (sch.get("issues") or []))
    recs = _collect_recommendations(issues)

    md = []
    md.append("# OpenAPI Quality Report")
    md.append(f"**Overall Score:** {overall}/100\n")
    md.append("## Category Scores")
    md.append(f"- **Documentation Quality:** {doc.get('score', 0)}")
    md.append(f"- **Schema Completeness:** {sch.get('score', 0)}\n")

    md.append("## Issues")
    if issues:
        for i in issues:
            md.append(f"- {i}")
    else:
        md.append("- No issues found 🎉")
    md.append("")

    md.append("## Recommendations")
    if recs:
        for r in recs:
            md.append(f"- {r}")
    else:
        md.append("- None — great job!")
    return "\n".join(md)


def render_json(results: Dict[str, Any]) -> str:
    """
    Render a JSON report (for automation/CI).
    """
    # Attach derived recommendations as well
    doc = results.get("documentation_quality", {})
    sch = results.get("schema_completeness", {})
    issues = _sorted_issues((doc.get("issues") or []) + (sch.get("issues") or []))
    recs = _collect_recommendations(issues)

    payload = {
        "overall_score": results.get("overall_score", 0),
        "documentation_quality": doc,
        "schema_completeness": sch,
        "issues": issues,
        "recommendations": recs,
    }
    return json.dumps(payload, indent=2)


def generate_report(results: Dict[str, Any], fmt: str = "text") -> str:
    """
    Generate a report from scorecard results in a chosen format.
    fmt ∈ {"text","markdown","json"}
    """
    fmt = (fmt or "text").lower()
    if fmt == "markdown":
        return render_markdown(results)
    if fmt == "json":
        return render_json(results)
    return render_text(results)

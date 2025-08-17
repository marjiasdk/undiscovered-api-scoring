#!/usr/bin/env python3
"""
Streamlit Web App for OpenAPI Quality Scorecard (extended UI)
- Upload OpenAPI spec(s)
- Scores, baseline comparison, charts
- Issues & Recommendations with severity
- History tracking
- Export: JSON, HTML, Markdown
- Multi-spec comparison
"""

from __future__ import annotations
import json
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd
import streamlit as st
import altair as alt


# --- Import core modules ---
from parser import OpenAPIParser
from scorecard import run_scorecard
from benchmarks import DEFAULT_BASELINE, compare_to_baseline, aggregate_common_issues
from history import append_run, get_trend

# Fallback helpers if report_cli not importable
try:
    from report_cli import flatten, category_rows, render_html as _render_html
except Exception:

    def flatten(results: Dict) -> Dict:
        issues, recs = [], []
        for k, v in results.items():
            if isinstance(v, dict):
                issues += v.get("issues", [])
                recs += v.get("recommendations", [])
        results["issues"] = issues
        results["recommendations"] = recs
        return results

    def category_rows(results: Dict) -> List[Tuple[str, int]]:
        rows = []
        for k, v in results.items():
            if isinstance(v, dict) and "score" in v:
                rows.append((k.replace("_", " ").title(), v["score"]))
        return rows

    def _render_html(
        spec_name: str, res: Dict, baseline_cmp: Dict, trend: List, outfile: str
    ):
        html = [
            f"<h1>OpenAPI Quality Report — {spec_name}</h1>",
            f"<p><b>Overall:</b> {res.get('overall_score', 0)}/100</p>",
            "<h2>Category Scores</h2><ul>",
        ]
        for name, score in category_rows(res):
            html.append(f"<li>{name}: {score}</li>")
        html.append("</ul><h2>Issues</h2><ul>")
        for i in res.get("issues", []):
            html.append(f"<li>{i}</li>")
        html.append("</ul><h2>Recommendations</h2><ul>")
        for r in res.get("recommendations", []):
            html.append(f"<li>{r}</li>")
        html.append("</ul>")
        Path(outfile).write_text("\n".join(html), encoding="utf-8")


# ---------- Page Config & CSS ----------
st.set_page_config(page_title="API Quality Scorecard", layout="wide")

st.markdown(
    """
<style>
:root{
  --bg:#0b1220; --card:#111a2b; --muted:#a7b0c0; --text:#e9eef8;
  --accent:#5bbcff; --good:#19c37d; --bad:#ff6b6b; --warn:#ffd166; --border:#1e2a44;
}
@media (prefers-color-scheme: light){
  :root{
    --bg:#f6f8fc; --card:#ffffff; --muted:#4b5563; --text:#111827;
    --accent:#2563eb; --good:#16a34a; --bad:#dc2626; --warn:#d97706; --border:#e5e7eb;
  }
}
html, body, .block-container{ background: var(--bg); color: var(--text); }
.card{
  background: var(--card); border:1px solid var(--border); border-radius:14px; padding:16px; margin-bottom:16px;
}
.pill{ padding:6px 10px; border-radius:999px; background:var(--card); border:1px solid var(--border); color:var(--muted); }
.badge{ font-size:12px; padding:4px 8px; border-radius:999px; border:1px solid var(--border); background: rgba(127,127,127,.12); color:var(--muted); }
.badge.pass{ color: var(--good); border-color: rgba(25,195,125,.35); background: rgba(25,195,125,.08); }
.badge.fail{ color: var(--bad); border-color: rgba(255,107,107,.35); background: rgba(255,107,107,.08); }
.progress{ width:100%; height:10px; background: rgba(127,127,127,.15); border-radius:999px; overflow:hidden; border:1px solid var(--border); }
.progress > span{ display:block; height:100%; background:linear-gradient(90deg, var(--accent), #9b7bff); }
.sev{ padding:2px 6px; border-radius:999px; font-size:11px; margin-left:6px }
.sev-hi{ background:#ff6b6b22; color:#ff6b6b; border:1px solid #ff6b6b55 }
.sev-med{ background:#ffd16622; color:#d97706; border:1px solid #d9770655 }
.sev-lo{ background:#19c37d22; color:#19c37d; border:1px solid #19c37d55 }
.small-muted{ color: var(--muted); font-size:12px }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🔎 API Quality Scorecard (Web)")

# ---------- Sidebar Options ----------
with st.sidebar:
    st.header("Options")
    log_history = st.checkbox("Log to history (enables trend)", value=True)
    custom_baseline_file = st.file_uploader("Baseline (JSON, optional)", type=["json"])
    if custom_baseline_file:
        try:
            BASELINE = json.loads(custom_baseline_file.read().decode("utf-8"))
            st.success("Custom baseline loaded")
        except Exception as e:
            st.error(f"Failed to load baseline: {e}")
            BASELINE = DEFAULT_BASELINE
    else:
        BASELINE = DEFAULT_BASELINE

# ---------- Spec Input ----------
uploaded = st.file_uploader(
    "Upload an OpenAPI spec (YAML or JSON)", type=["yaml", "yml", "json"]
)
raw_text = st.text_area("…or paste YAML/JSON here (optional)", height=160)

if not uploaded and not raw_text.strip():
    st.info("👆 Upload a spec or paste content to begin.")
    st.stop()

# ---------- Parse Spec ----------
spec_name = "uploaded-spec"
spec_dict: Dict[str, Any]

try:
    if uploaded:
        spec_name = uploaded.name
        content = uploaded.read().decode("utf-8")
    else:
        content = raw_text

    if hasattr(OpenAPIParser, "from_string"):
        spec_dict = OpenAPIParser.from_string(content)
    else:
        tmp = Path("tmp_openapi_upload.yaml")
        tmp.write_text(content, encoding="utf-8")
        spec_dict = OpenAPIParser(tmp).load_spec()
except Exception as e:
    st.error(f"Failed to parse spec: {e}")
    st.stop()

# ---------- Analyze ----------
results = run_scorecard(spec_dict)
results = flatten(results)
baseline_cmp = compare_to_baseline(results, BASELINE)

# History
trend = get_trend(spec_name)
if log_history:
    append_run(spec_name, results)
    trend = get_trend(spec_name)

# ---------- Summary Metrics ----------
colA, colB, colC, colD = st.columns(4)
colA.metric("Overall Score", f"{results.get('overall_score', 0)}/100")
colB.metric("Issues Found", len(results.get("issues", [])))
colC.metric("Recommendations", len(results.get("recommendations", [])))
colD.metric("Categories", len([k for k, v in results.items() if isinstance(v, dict)]))

# ---------- Category Scores ----------
with st.container():
    st.markdown("<div class='card'><h4>Category Scores</h4>", unsafe_allow_html=True)
    left, right = st.columns([1.2, 1])
    with left:
        for label, score in category_rows(results):
            row = f"""
            <div style="display:flex; align-items:center; gap:10px; margin:8px 0;">
              <div style="min-width:210px">{label}</div>
              <div class="progress"><span style="width:{score}%"></span></div>
              <div class="pill" style="min-width:54px; text-align:center">{score}</div>
            </div>
            """
            st.markdown(row, unsafe_allow_html=True)

with right:
    try:
        labels = [n for (n, _) in category_rows(results)]
        your_scores = [s for (_, s) in category_rows(results)]
        baseline_thresholds = []
        for key in [l.replace(" ", "_").lower() for l in labels]:
            baseline_thresholds.append(BASELINE.get("min_scores", {}).get(key, 80))

        df = pd.DataFrame(
            {
                "Category": labels,
                "Your score": your_scores,
                "Baseline threshold": baseline_thresholds,
            }
        )

        # Melt for grouped bar chart
        df_long = df.melt("Category", var_name="Metric", value_name="Score")

        chart = (
            alt.Chart(df_long)
            .mark_bar()
            .encode(
                x=alt.X(
                    "Category:N", axis=alt.Axis(labelAngle=0)
                ),  # force horizontal labels
                y=alt.Y("Score:Q"),
                color="Metric:N",
                tooltip=["Category", "Metric", "Score"],
            )
            .properties(width="container", height=300)
        )
        st.altair_chart(chart, use_container_width=True)
        st.caption("Your scores vs baseline thresholds")
    except Exception:
        st.bar_chart({name: score for name, score in category_rows(results)})


# ---------- Baseline Comparison ----------
with st.container():
    st.markdown(
        "<div class='card'><h4>Baseline Comparison</h4>", unsafe_allow_html=True
    )
    rows = []
    for k, passed in baseline_cmp["passes"].items():
        delta = baseline_cmp["deltas"][k]
        rows.append(
            {
                "Category": k.replace("_", " ").title(),
                "Status": "PASS" if passed else "FAIL",
                "Δ vs threshold": f"{delta:+d}",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if baseline_cmp.get("notes"):
        st.caption(" ".join(baseline_cmp["notes"]))
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Trend ----------
with st.container():
    st.markdown("<div class='card'><h4>Trend</h4>", unsafe_allow_html=True)
    if len(trend) >= 2:
        t_series = pd.DataFrame(
            {
                "time": [dt.datetime.fromtimestamp(ts) for ts, _, _ in trend],
                "overall": [o for _, o, _ in trend],
            }
        ).set_index("time")
        st.line_chart(t_series)
    else:
        st.caption("No history yet — enable 'Log to history' and analyze a few times.")
    st.markdown("</div>", unsafe_allow_html=True)


# ---------- Issues & Recommendations ----------
# ---------- Issues & Recommendations (Grouped by Category) ----------


def severity(issue: str) -> str:
    i = issue.lower()
    if "5xx" in i or "4xx" in i or "error response" in i:
        return "hi"
    if (
        "auth" in i
        or "security" in i
        or "missing description" in i
        or "discoverability" in i
    ):
        return "med"
    return "lo"


st.markdown(
    "<div class='card'><h4>Issues & Recommendations (by Category)</h4>",
    unsafe_allow_html=True,
)

# pull per-category dicts (each category is a dict with score, issues, recommendations)
category_blocks = {
    k: v for k, v in results.items() if isinstance(v, dict) and "score" in v
}

if not category_blocks:
    st.success("No issues 🎉")
else:
    # consistent order: by category name
    for cat_name in sorted(category_blocks.keys()):
        cat = category_blocks[cat_name]
        issues = cat.get("issues") or []
        recs = cat.get("recommendations") or []
        nice = cat_name.replace("_", " ").title()
        with st.expander(
            f"{nice} — {len(issues)} issue(s), {len(recs)} recommendation(s)"
        ):
            # Issues list
            if issues:
                st.markdown("**❗ Issues**")
                for i in issues:
                    sev = severity(i)
                    st.markdown(
                        f"<div style='margin-bottom:8px'><span class='sev sev-{sev}'>"
                        f"{'HIGH' if sev=='hi' else 'MED' if sev=='med' else 'LOW'}</span> &nbsp; {i}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.success("No issues in this category 🎉")

            # Recommendations list
            if recs:
                st.markdown("**💡 Recommendations**")
                for r in recs:
                    st.markdown(f"- {r}")
            else:
                st.info("No recommendations for this category")

st.markdown("</div>", unsafe_allow_html=True)


# ---------- Export ----------
st.markdown("<div class='card'><h4>Export</h4>", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)

payload = {
    "spec": spec_name,
    "results": results,
    "baseline": baseline_cmp,
    "trend": trend,
}

with col1:
    st.download_button(
        "⬇️ JSON",
        data=json.dumps(payload, indent=2).encode("utf-8"),
        file_name=f"{spec_name}.report.json",
        mime="application/json",
    )

with col2:
    tmp_html = Path(f"{spec_name}.report.html")
    _render_html(spec_name, results, baseline_cmp, trend, str(tmp_html))
    st.download_button(
        "⬇️ HTML",
        data=tmp_html.read_bytes(),
        file_name=tmp_html.name,
        mime="text/html",
    )

with col3:
    md_out = [
        f"# API Quality Report — {spec_name}\n",
        f"**Overall Score:** {results.get('overall_score', 0)}/100\n",
        "## Category Scores",
    ]
    for n, s in category_rows(results):
        md_out.append(f"- **{n}:** {s}")
    md_out.append("\n## Issues")
    for i in results.get("issues", []):
        md_out.append(f"- {i}")
    md_out.append("\n## Recommendations")
    for r in results.get("recommendations", []):
        md_out.append(f"- {r}")
    st.download_button(
        "⬇️ Markdown",
        data="\n".join(md_out).encode("utf-8"),
        file_name=f"{spec_name}.report.md",
        mime="text/markdown",
    )

st.caption("Generated by API Quality Scorecard")

# ---------- Raw JSON Debug ----------
with st.expander("🔍 Raw JSON Output"):
    st.json(payload)

# ---------- Multi-Spec Comparison ----------
st.markdown(
    "<div class='card'><h4>🆚 Multi-Spec Comparison</h4>", unsafe_allow_html=True
)
multi_specs = st.file_uploader(
    "Upload multiple specs", type=["yaml", "yml", "json"], accept_multiple_files=True
)
if multi_specs:
    comp_data, all_results = {}, []
    for sp in multi_specs:
        try:
            name = sp.name
            text = sp.read().decode("utf-8")
            if hasattr(OpenAPIParser, "from_string"):
                spec = OpenAPIParser.from_string(text)
            else:
                tmp = Path("tmp_multi.yaml")
                tmp.write_text(text, encoding="utf-8")
                spec = OpenAPIParser(tmp).load_spec()
            r = flatten(run_scorecard(spec))
            comp_data[name] = {n: s for n, s in category_rows(r)}
            all_results.append(r)
        except Exception as e:
            st.error(f"Failed to parse {sp.name}: {e}")

    if comp_data:
        df = pd.DataFrame(comp_data).T
        st.bar_chart(df)
        st.caption("Category scores across multiple APIs")

        st.markdown("### Common Issues Across APIs")
        issues = aggregate_common_issues(all_results, top_n=10)
        for issue, count in issues:
            st.markdown(f"- {issue} ({count} APIs)")

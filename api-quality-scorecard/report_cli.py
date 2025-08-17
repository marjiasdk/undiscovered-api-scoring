#!/usr/bin/env python3
"""
Report CLI for OpenAPI Scorecard — Detailed (Task 7 + 9)
- Text, JSON, Markdown, HTML
- Multi-spec comparison
- Baseline/best-practice comparison
- History logging & trend charts
- Common issues aggregation and industry benchmarks
"""

import argparse, json, os
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
from jinja2 import Template

from parser import OpenAPIParser
from scorecard import run_scorecard
from history import append_run, get_trend, load_history
from benchmarks import (
    DEFAULT_BASELINE,
    compare_to_baseline,
    aggregate_common_issues,
    compute_industry_benchmarks,
)


# ---------- Helpers ----------


def flatten(results: Dict) -> Dict:
    issues, recs = [], []
    for k, v in results.items():
        if isinstance(v, dict):
            issues += v.get("issues", [])
            recs += v.get("recommendations", [])
    results["issues"] = issues
    results["recommendations"] = recs
    return results


def load_baseline(path: str | None) -> Dict:
    if not path:
        return DEFAULT_BASELINE
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def category_rows(results: Dict) -> List[tuple]:
    rows = []
    for k, v in results.items():
        if isinstance(v, dict) and "score" in v:
            rows.append((k.replace("_", " ").title(), v["score"]))
    return rows


# ---------- Renderers ----------


def render_text(
    spec_name: str,
    res: Dict,
    baseline_cmp: Dict | None,
    trend: List,
    multi: bool = False,
) -> str:
    lines = []
    if multi:
        lines.append(f"\n=== {spec_name} ===")
    lines.append("OpenAPI Quality Report")
    lines.append("=" * 24)
    lines.append(f"Overall Score: {res['overall_score']}/100\n")

    lines.append("Category Scores")
    for name, score in category_rows(res):
        lines.append(f"- {name:22}: {score}")

    if baseline_cmp:
        lines.append("\nBaseline Comparison (pass/Δ vs threshold)")
        for k, passed in baseline_cmp["passes"].items():
            delta = baseline_cmp["deltas"][k]
            lines.append(
                f"- {k.replace('_',' ').title():22}: {'PASS' if passed else 'FAIL'} (Δ={delta:+})"
            )
        for note in baseline_cmp.get("notes", []):
            lines.append(f"  • {note}")

    if trend:
        lines.append("\nTrend (most recent 5):")
        tail = trend[-5:]
        for ts, overall, cats in tail:
            lines.append(
                f"- {ts}: overall {overall}, "
                + ", ".join(f"{k[:3]}={v}" for k, v in cats.items())
            )

    lines.append("\nIssues")
    for issue in res.get("issues", []):
        lines.append(f"  • {issue}")

    lines.append("\nRecommendations")
    for rec in res.get("recommendations", []):
        lines.append(f"  • {rec}")

    return "\n".join(lines)


def render_markdown(
    spec_name: str, res: Dict, baseline_cmp: Dict | None, trend: List
) -> str:
    md = [
        f"# OpenAPI Quality Report — {spec_name}\n",
        f"**Overall Score:** {res['overall_score']}/100\n",
        "## Category Scores",
    ]
    for name, score in category_rows(res):
        md.append(f"- **{name}**: {score}")

    if baseline_cmp:
        md.append("\n## Baseline Comparison")
        for k, passed in baseline_cmp["passes"].items():
            delta = baseline_cmp["deltas"][k]
            md.append(
                f"- **{k.replace('_',' ').title()}**: {'PASS' if passed else 'FAIL'} (Δ={delta:+})"
            )
        if baseline_cmp.get("notes"):
            md.append("\n> " + " ".join(baseline_cmp["notes"]))

    if trend:
        md.append("\n## Trend (last 5)")
        tail = trend[-5:]
        for ts, overall, cats in tail:
            md.append(
                f"- `{ts}`: overall **{overall}**, "
                + ", ".join(f"{k}={v}" for k, v in cats.items())
            )

    md.append("\n## Issues")
    for issue in res.get("issues", []):
        md.append(f"- {issue}")

    md.append("\n## Recommendations")
    for rec in res.get("recommendations", []):
        md.append(f"- {rec}")

    return "\n".join(md)


def _save_trend_chart(spec_name: str, trend: List, outfile_stem: str) -> str | None:
    if not trend:
        return None
    xs = [t for (t, _, _) in trend]
    ys = [o for (_, o, _) in trend]
    plt.figure(figsize=(6, 3))
    plt.plot(xs, ys, marker="o")
    plt.ylim(0, 100)
    plt.title(f"Overall Score Trend — {spec_name}")
    plt.xlabel("timestamp")
    plt.ylabel("score")
    chart_file = f"{outfile_stem}_trend.png"
    plt.savefig(chart_file, bbox_inches="tight")
    plt.close()
    return chart_file


def _save_bar_chart(spec_name: str, res: Dict, outfile_stem: str) -> str:
    cats = [n for (n, _) in category_rows(res)]
    vals = [s for (_, s) in category_rows(res)]
    plt.figure(figsize=(7, 3.5))
    plt.bar(cats, vals)
    plt.ylim(0, 100)
    plt.xticks(rotation=20)
    plt.title(f"Category Scores — {spec_name}")
    plt.ylabel("score")
    chart_file = f"{outfile_stem}_cats.png"
    plt.savefig(chart_file, bbox_inches="tight")
    plt.close()
    return chart_file


def render_html(
    spec_name: str, res: Dict, baseline_cmp: Dict | None, trend: List, outfile: str
):
    # Prepare data for charts
    cat_labels = [name for (name, _) in category_rows(res)]
    cat_scores = [score for (_, score) in category_rows(res)]

    # Tiny trend arrays (timestamps -> labels)
    tr_x = [str(t) for (t, _, _) in trend][-12:]  # last 12 points
    tr_y = [o for (_, o, _) in trend][-12:]

    # Baseline arrays (if any)
    bl_labels, bl_scores = [], []
    if baseline_cmp:
        # Use same labels order as category grid for the radar
        key_by_label = {name.replace(" ", "_").lower(): name for name in cat_labels}
        for k, delta in baseline_cmp["deltas"].items():
            label = key_by_label.get(k, k.replace("_", " ").title())
            bl_labels.append(label)
            bl_scores.append(
                baseline_cmp["deltas"][k]
            )  # deltas for coloring in table; radar uses thresholds below
    # Thresholds for radar
    radar_thresholds = []
    if baseline_cmp:
        # Use your DEFAULT_BASELINE values if present in the dict
        try:
            from benchmarks import DEFAULT_BASELINE as _BL

            for k in [l.replace(" ", "_").lower() for l in cat_labels]:
                radar_thresholds.append(_BL["min_scores"].get(k, 80))
        except Exception:
            radar_thresholds = [80] * len(cat_labels)
    else:
        radar_thresholds = [80] * len(cat_labels)

    # Pretty HTML (self-contained)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OpenAPI Quality Report — {spec_name}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {{
      --bg:#0b1220; --card:#111a2b; --muted:#a7b0c0; --text:#e9eef8; --accent:#5bbcff; --good:#19c37d; --bad:#ff6b6b; --warn:#ffd166;
      --border: #1e2a44;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg:#f6f8fc; --card:#ffffff; --muted:#4b5563; --text:#111827; --accent:#2563eb; --good:#16a34a; --bad:#dc2626; --warn:#d97706;
        --border:#e5e7eb;
      }}
    }}
    * {{ box-sizing: border-box }}
    body {{
      margin: 0; padding: 32px; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial, sans-serif;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; }}
    .header {{
      display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom: 18px;
    }}
    .title {{ font-size: 22px; font-weight: 700; letter-spacing: .2px; }}
    .pill {{ padding:6px 10px; border-radius:999px; background:var(--card); border:1px solid var(--border); color:var(--muted); }}
    .grid {{ display:grid; gap:16px; grid-template-columns: 1.2fr .8fr; }}
    .card {{ background: var(--card); border:1px solid var(--border); border-radius:14px; padding:16px; }}
    h2 {{ font-size:16px; margin:0 0 10px 0; }}
    .row {{ display:flex; gap:10px; align-items:center; justify-content:space-between; }}
    .progress {{
      width: 100%; height: 10px; background: rgba(127,127,127,.15); border-radius:999px; overflow:hidden; border:1px solid var(--border);
    }}
    .progress > span {{
      display:block; height:100%; background:linear-gradient(90deg, var(--accent), #9b7bff);
    }}
    .badge {{ font-size:12px; padding:4px 8px; border-radius:999px; border:1px solid var(--border); background: rgba(127,127,127,.12); color:var(--muted); }}
    .badge.pass {{ color: var(--good); border-color: rgba(25,195,125,.35); background: rgba(25,195,125,.08); }}
    .badge.fail {{ color: var(--bad); border-color: rgba(255,107,107,.35); background: rgba(255,107,107,.08); }}
    .list {{ margin:0; padding-left: 18px; }}
    .two {{ display:grid; grid-template-columns: 1fr 1fr; gap:16px; }}
    details {{ border:1px solid var(--border); background:var(--card); border-radius:10px; padding:10px 12px; }}
    details + details {{ margin-top:10px; }}
    summary {{ cursor:pointer; color: var(--muted); font-weight:600; }}
    .muted {{ color: var(--muted); }}
    .table {{ width:100%; border-collapse: collapse; }}
    .table th, .table td {{ padding:8px 10px; border-bottom:1px solid var(--border); text-align:left; }}
    .footer {{ margin-top:18px; color: var(--muted); font-size:12px; text-align:center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="title">OpenAPI Quality Report — {spec_name}</div>
      <div class="pill">Overall Score: <b>{res['overall_score']}</b>/100</div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Category Scores</h2>
        <div style="display:grid; gap:10px;">
          {"".join(f'''
          <div class="row">
            <div style="min-width:210px">{label}</div>
            <div class="progress"><span style="width:{score}%"></span></div>
            <div class="pill" style="min-width:54px; text-align:center">{score}</div>
          </div>''' for label, score in category_rows(res))}
        </div>
      </div>

      <div class="card">
        <h2>Overview</h2>
        <canvas id="barChart" height="180"></canvas>
        <div class="muted" style="margin-top:8px">Scores by category</div>
      </div>
    </div>

    <div class="two" style="margin-top:16px;">
      <div class="card">
        <h2>Baseline Comparison</h2>
        {"<div class='muted'>No baseline provided</div>" if not baseline_cmp else ""}
        {""
          if not baseline_cmp else
          "<table class='table'><thead><tr><th>Category</th><th>Status</th><th>Δ vs threshold</th></tr></thead><tbody>"
          + "".join(
            f"<tr><td>{k.replace('_',' ').title()}</td>"
            f"<td><span class='badge {'pass' if p else 'fail'}'>{'PASS' if p else 'FAIL'}</span></td>"
            f"<td>{'+' if baseline_cmp['deltas'][k] >= 0 else ''}{baseline_cmp['deltas'][k]}</td></tr>"
            for k, p in baseline_cmp['passes'].items()
          )
          + "</tbody></table>"
        }
        <div style="margin-top:10px;">
          {"".join(f"<span class='badge' style='margin-right:6px'>{note}</span>" for note in (baseline_cmp.get('notes') or []))}
        </div>
      </div>

      <div class="card">
        <h2>Benchmark Radar</h2>
        <canvas id="radarChart" height="200"></canvas>
        <div class="muted" style="margin-top:8px">Your score vs baseline thresholds</div>
      </div>
    </div>

    <div class="two" style="margin-top:16px;">
      <div class="card">
        <h2>Issues</h2>
        {"<div class='muted'>No issues found 🎉</div>" if not res.get('issues') else ""}
        {"".join(f"<details><summary>{i.split(':')[0]}</summary><div class='muted' style='margin-top:8px'>{i}</div></details>" for i in res.get('issues', []))}
      </div>
      <div class="card">
        <h2>Recommendations</h2>
        {"<div class='muted'>No recommendations</div>" if not res.get('recommendations') else ""}
        {"".join(f"<details><summary>{r.split(':')[0]}</summary><div class='muted' style='margin-top:8px'>{r}</div></details>" for r in res.get('recommendations', []))}
      </div>
    </div>

    <div class="card" style="margin-top:16px;">
      <h2>Trend</h2>
      <canvas id="trendChart" height="170"></canvas>
      <div class="muted" style="margin-top:8px">Overall score across runs (history)</div>
    </div>

    <div class="footer">Generated by API Quality Scorecard</div>
  </div>

  <script>
    const catLabels = {json.dumps(cat_labels)};
    const catScores = {json.dumps(cat_scores)};
    const trendX = {json.dumps(tr_x)};
    const trendY = {json.dumps(tr_y)};
    const thresholds = {json.dumps(radar_thresholds)};

    // Category bar
    new Chart(document.getElementById('barChart'), {{
      type: 'bar',
      data: {{
        labels: catLabels,
        datasets: [{{
          label: 'Score',
          data: catScores,
          borderWidth: 1
        }}]
      }},
      options: {{
        plugins: {{ legend: {{ display:false }} }},
        scales: {{
          y: {{ beginAtZero:true, max:100 }}
        }}
      }}
    }});

    // Trend line (render only if we have 2+ points)
    if (trendY.length >= 2) {{
      new Chart(document.getElementById('trendChart'), {{
        type: 'line',
        data: {{
          labels: trendX,
          datasets: [{{
            label: 'Overall',
            data: trendY,
            fill: false,
            tension: .25
          }}]
        }},
        options: {{
          plugins: {{ legend: {{ display:false }} }},
          scales: {{
            y: {{ beginAtZero:true, max:100 }}
          }}
        }}
      }});
    }} else {{
      document.getElementById('trendChart').replaceWith((() => {{
        const d = document.createElement('div');
        d.className = 'muted';
        d.style.padding = '8px 0';
        d.textContent = 'No history yet — run with --update-history a few times';
        return d;
      }})());
    }}

    // Radar chart (scores vs thresholds)
    new Chart(document.getElementById('radarChart'), {{
      type: 'radar',
      data: {{
        labels: catLabels,
        datasets: [
          {{
            label: 'Your score',
            data: catScores
          }},
          {{
            label: 'Baseline threshold',
            data: thresholds
          }}
        ]
      }},
      options: {{
        plugins: {{ legend: {{ display: true }} }},
        scales: {{
          r: {{ suggestedMin: 0, suggestedMax: 100, ticks: {{ stepSize: 20 }} }}
        }}
      }}
    }});
  </script>
</body>
</html>
"""
    Path(outfile).write_text(html, encoding="utf-8")
    print(f"✅ HTML report saved to {outfile}")


# ---------- CLI ----------


def main():
    ap = argparse.ArgumentParser(
        description="OpenAPI Scorecard — Detailed Reports, Baselines & Trends"
    )
    ap.add_argument("--spec", nargs="+", required=True, help="OpenAPI spec file(s)")
    ap.add_argument("--format", choices=["text", "json", "md", "html"], default="text")
    ap.add_argument("--output", help="Output file (for md/json/html)")
    ap.add_argument("--baseline", help="JSON file with baseline thresholds (optional)")
    ap.add_argument(
        "--history-file",
        default=".scorecard/history.json",
        help="Path to score history file",
    )
    ap.add_argument(
        "--update-history", action="store_true", help="Append this run(s) to history"
    )
    args = ap.parse_args()

    baseline = load_baseline(args.baseline)
    results_per_spec: List[tuple[str, Dict]] = []

    # Process each spec
    for spec_path in args.spec:
        spec_name = Path(spec_path).name
        spec = OpenAPIParser(spec_path).load_spec()
        res = run_scorecard(spec)
        flatten(res)

        # Baseline compare
        baseline_cmp = compare_to_baseline(res, baseline)

        # Trend from history
        trend = get_trend(spec_name, args.history_file)

        # Save to history if requested
        if args.update_history:
            append_run(spec_name, res, args.history_file)

        results_per_spec.append((spec_name, res, baseline_cmp, trend))

    # Multi-spec comparison mode
    if len(results_per_spec) > 1:
        # Aggregate “industry” stats & common issues
        only_results = [r for (_, r, _, _) in results_per_spec]
        common = aggregate_common_issues(only_results, top_n=10)
        bench = compute_industry_benchmarks(only_results)

        if args.format == "json":
            payload = {
                "comparison": {name: r for (name, r, _, _) in results_per_spec},
                "common_issues": common,
                "benchmarks": bench,
            }
            out = json.dumps(payload, indent=2)
            if args.output:
                Path(args.output).write_text(out, encoding="utf-8")
                print(f"✅ JSON comparison saved to {args.output}")
            else:
                print(out)
            return

        if args.format == "md":
            lines = ["# OpenAPI Comparison Report\n"]
            for name, res, base_cmp, trend in results_per_spec:
                lines.append(f"## {name}\n**Overall:** {res['overall_score']}/100")
                for cn, sc in category_rows(res):
                    lines.append(f"- **{cn}**: {sc}")
                lines.append("")
            lines.append("## Common Issues")
            for iss, n in common:
                lines.append(f"- {iss} _(x{n})_")
            lines.append("\n## Industry Benchmarks (mean/median, n)")
            for cat, s in bench.items():
                lines.append(
                    f"- **{cat.replace('_',' ').title()}**: mean {s['mean']}, median {s['median']} (n={s['n']})"
                )
            out = "\n".join(lines)
            if args.output:
                Path(args.output).write_text(out, encoding="utf-8")
                print(f"✅ Markdown comparison saved to {args.output}")
            else:
                print(out)
            return

        # Text & HTML (text prints, HTML not aggregated into one file for simplicity)
        if args.format == "text":
            print("📊 Comparison Report")
            for name, res, _, _ in results_per_spec:
                print(f"- {name}: Overall {res['overall_score']}")
            print("\nTop Common Issues:")
            for iss, n in common:
                print(f"  • {iss} (x{n})")
            print("\nIndustry Benchmarks:")
            for cat, s in bench.items():
                print(
                    f"  • {cat.replace('_',' ').title()}: mean {s['mean']} / median {s['median']} (n={s['n']})"
                )
            return

        if args.format == "html":
            # For now, emit one HTML per spec + print an industry summary to stdout
            print("ℹ️ Generating one HTML per spec; industry summary printed below.")
            for name, res, base_cmp, trend in results_per_spec:
                outfile = args.output or f"{name}_report.html"
                render_html(name, res, base_cmp, trend, outfile)
            print("\nIndustry Benchmarks:")
            for cat, s in bench.items():
                print(
                    f"- {cat.replace('_',' ').title()}: mean {s['mean']}, median {s['median']} (n={s['n']})"
                )
            print("\nTop Common Issues:")
            for iss, n in common:
                print(f"- {iss} (x{n})")
            return

    # Single-spec report
    name, res, base_cmp, trend = results_per_spec[0]
    if args.format == "json":
        out = json.dumps(
            {"spec": name, "results": res, "baseline": base_cmp, "trend": trend},
            indent=2,
        )
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
            print(f"✅ JSON report saved to {args.output}")
        else:
            print(out)
    elif args.format == "md":
        out = render_markdown(name, res, base_cmp, trend)
        if args.output:
            Path(args.output).write_text(out, encoding="utf-8")
            print(f"✅ Markdown report saved to {args.output}")
        else:
            print(out)
    elif args.format == "html":
        outfile = args.output or f"{name}_report.html"
        render_html(name, res, base_cmp, trend, outfile)
    else:
        print(render_text(name, res, base_cmp, trend))


if __name__ == "__main__":
    main()

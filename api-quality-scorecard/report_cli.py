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
    stem = os.path.splitext(outfile)[0]
    cats_png = _save_bar_chart(spec_name, res, stem)
    trend_png = _save_trend_chart(spec_name, trend, stem)

    tpl = Template(
        """
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>OpenAPI Quality Report — {{ spec_name }}</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 30px; }
        h1 { color: #2c3e50; }
        h2 { margin-top: 28px; }
        ul { line-height: 1.6; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        .muted { color: #666; font-size: 0.9em; }
        .pass { color: #2e7d32; }
        .fail { color: #c62828; }
      </style>
    </head>
    <body>
      <h1>OpenAPI Quality Report — {{ spec_name }}</h1>
      <p><strong>Overall Score:</strong> {{ res.overall_score }}/100</p>

      <div class="grid">
        <div>
          <h2>Category Scores</h2>
          <ul>
            {% for name, score in cat_rows %}
              <li><strong>{{ name }}</strong>: {{ score }}</li>
            {% endfor %}
          </ul>
        </div>
        <div>
          <h2>Visualization</h2>
          <img src="{{ cats_png }}" width="100%%" />
          {% if trend_png %}
            <p class="muted">Overall trend:</p>
            <img src="{{ trend_png }}" width="100%%" />
          {% endif %}
        </div>
      </div>

      {% if baseline_cmp %}
      <h2>Baseline Comparison</h2>
      <ul>
        {% for k, passed in baseline_cmp.passes.items() %}
          <li>{{ k.replace('_',' ').title() }}:
            <span class="{{ 'pass' if passed else 'fail' }}">
              {{ 'PASS' if passed else 'FAIL' }}
            </span>
            (Δ={% if baseline_cmp.deltas[k] is not none %}{{ "%+d"|format(baseline_cmp.deltas[k]) }}{% else %}+0{% endif %})
          </li>
        {% endfor %}
      </ul>
      {% if baseline_cmp.notes %}
        <p class="muted">Notes: {{ ' '.join(baseline_cmp.notes) }}</p>
      {% endif %}
      {% endif %}

      <h2>Issues</h2>
      <ul>
        {% for i in res.issues %}<li>{{ i }}</li>{% endfor %}
      </ul>

      <h2>Recommendations</h2>
      <ul>
        {% for r in res.recommendations %}<li>{{ r }}</li>{% endfor %}
      </ul>
    </body>
    </html>
    """
    )

    html = tpl.render(
        spec_name=spec_name,
        res=res,
        baseline_cmp=baseline_cmp,
        cat_rows=category_rows(res),
        cats_png=os.path.basename(cats_png),
        trend_png=os.path.basename(trend_png) if trend_png else None,
    )
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

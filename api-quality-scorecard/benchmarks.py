# benchmarks.py
from __future__ import annotations
from typing import Dict, List, Tuple
from statistics import mean, median

# Default best practices (edit as needed)
DEFAULT_BASELINE = {
    "min_scores": {
        "documentation_quality": 90,
        "schema_completeness": 85,
        "agent_usability": 90,
        "error_handling": 80,
        "authentication": 80,
    },
    "required_error_codes": ["400", "404", "500"],
    "error_schema_required_fields": ["error", "message"],
    "auth_required": True,
}


def compare_to_baseline(results: Dict, baseline: Dict = DEFAULT_BASELINE) -> Dict:
    """Return pass/fail + deltas vs baseline thresholds."""
    out = {"passes": {}, "deltas": {}, "notes": []}
    mins = baseline.get("min_scores", {})
    for cat, threshold in mins.items():
        score = results.get(cat, {}).get("score", 0)
        out["passes"][cat] = score >= threshold
        out["deltas"][cat] = score - threshold
    # Simple doc notes based on auth/error presence
    if baseline.get("auth_required", True):
        if results.get("authentication", {}).get("score", 0) < mins.get(
            "authentication", 0
        ):
            out["notes"].append("Authentication docs under baseline expectations.")
    if results.get("error_handling", {}).get("score", 0) < mins.get(
        "error_handling", 0
    ):
        out["notes"].append(
            "Error handling below baseline; add 4xx/5xx responses with schemas."
        )
    return out


def aggregate_common_issues(
    result_list: List[Dict], top_n: int = 10
) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for r in result_list:
        for cat, data in r.items():
            if isinstance(data, dict):
                for issue in data.get("issues", []):
                    counts[issue] = counts.get(issue, 0) + 1
    # Sort by frequency desc, then alpha
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]


def compute_industry_benchmarks(result_list: List[Dict]) -> Dict[str, Dict[str, float]]:
    """Compute mean/median per category across many APIs."""
    cats = {}
    for r in result_list:
        for k, v in r.items():
            if isinstance(v, dict) and "score" in v:
                cats.setdefault(k, []).append(v["score"])
    summary = {}
    for k, vals in cats.items():
        if not vals:
            continue
        vals_sorted = sorted(vals)
        summary[k] = {
            "mean": round(mean(vals), 1),
            "median": round(median(vals), 1),
            "min": min(vals_sorted),
            "max": max(vals_sorted),
            "n": len(vals_sorted),
        }
    return summary

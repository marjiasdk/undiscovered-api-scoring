# history.py
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_HISTORY = Path("history.json")


def load_history(path: str | Path = DEFAULT_HISTORY) -> Dict:
    p = Path(path)
    if not p.exists():
        return {"runs": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"runs": []}


def save_history(data: Dict, path: str | Path = DEFAULT_HISTORY) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_run(
    spec_name: str, results: Dict, path: str | Path = DEFAULT_HISTORY
) -> None:
    data = load_history(path)
    entry = {
        "ts": int(time.time()),
        "spec": spec_name,
        "overall": results.get("overall_score", 0),
        "categories": {
            k: v["score"]
            for k, v in results.items()
            if isinstance(v, dict) and "score" in v
        },
    }
    data.setdefault("runs", []).append(entry)
    save_history(data, path)


def get_trend(
    spec_name: str, path: str | Path = DEFAULT_HISTORY
) -> List[Tuple[int, int, Dict[str, int]]]:
    """Return list of (timestamp, overall, per-category scores) for spec_name sorted by time."""
    data = load_history(path)
    rows = [
        (r["ts"], r.get("overall", 0), r.get("categories", {}))
        for r in data.get("runs", [])
        if r.get("spec") == spec_name
    ]
    rows.sort(key=lambda x: x[0])
    return rows


def last_scores(
    spec_name: str, path: str | Path = DEFAULT_HISTORY
) -> Dict[str, int] | None:
    trend = get_trend(spec_name, path)
    return trend[-1][2] if trend else None

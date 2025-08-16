#!/usr/bin/env python3
"""
validator.py — Minimal validation utilities for the ArcGIS OpenAPI specs

Features:
1) Lint each OpenAPI file for basic structure.
2) Count endpoints (path + method combos).
3) Check for the canonical operationIds used in this project.
4) Optional live tests (no auth) to verify a couple endpoints still respond.

Usage:
  python validator.py lint --spec portal.openapi.yaml --spec services.openapi.yaml
  python validator.py count --spec openapi.yaml
  python validator.py ops --spec openapi.yaml
  python validator.py live-portal
  python validator.py live-services

Notes:
- 'live-*' commands perform real HTTP GET calls against public ArcGIS endpoints;
  use them only if you have network access and agree to call public services.
- This script avoids external dependencies except PyYAML and requests.
  Install them if needed: pip install pyyaml requests
"""
import argparse, sys, re
from typing import Dict, Any, List, Tuple, Set

def _load_yaml(path: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as e:
        print("PyYAML is required for reading specs. Install with: pip install pyyaml", file=sys.stderr)
        raise
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def lint_spec(spec: Dict[str, Any]) -> List[str]:
    errors = []
    if not isinstance(spec, dict):
        errors.append("Spec is not a mapping/dict.")
        return errors
    if "openapi" not in spec:
        errors.append("Missing top-level 'openapi' key.")
    if "info" not in spec or not isinstance(spec["info"], dict):
        errors.append("Missing or invalid 'info' object.")
    if "paths" not in spec or not isinstance(spec["paths"], dict) or not spec["paths"]:
        errors.append("Missing or empty 'paths'.")
    # Optional warnings
    if "servers" not in spec or not isinstance(spec["servers"], list) or not spec["servers"]:
        errors.append("Warning: no 'servers' defined; runners may fail without a host.")
    return errors

def count_endpoints(spec: Dict[str, Any]) -> int:
    total = 0
    for path, item in spec.get("paths", {}).items():
        if not isinstance(item, dict): 
            continue
        for method, op in item.items():
            if method.lower() in {"get","post","put","patch","delete","options","head","trace"}:
                total += 1
    return total

def collect_operation_ids(spec: Dict[str, Any]) -> Set[str]:
    ops = set()
    for path, item in spec.get("paths", {}).items():
        if not isinstance(item, dict): 
            continue
        for method, op in item.items():
            if method.lower() in {"get","post","put","patch","delete","options","head","trace"}:
                oid = op.get("operationId")
                if oid:
                    ops.add(oid)
    return ops

CANONICAL_OPS = {
    "searchItems",
    "getItemMetadata",
    "getItemData",
    "describeFeatureServer",
    "describeFeatureLayerGeneric",
    "queryFeatureLayerGeneric",
}

def cmd_lint(args):
    any_error = False
    for path in args.spec:
        print(f"— Linting: {path}")
        try:
            spec = _load_yaml(path)
        except Exception as e:
            print(f"  ❌ Failed to read: {e}")
            any_error = True
            continue
        errs = lint_spec(spec)
        if errs:
            for e in errs:
                print(f"  ⚠️  {e}")
            # treat only hard errors as failure
            hard = [e for e in errs if not e.lower().startswith("warning")]
            if hard: any_error = True
        else:
            print("  ✅ Looks structurally OK")
    sys.exit(1 if any_error else 0)

def cmd_count(args):
    for path in args.spec:
        spec = _load_yaml(path)
        n = count_endpoints(spec)
        print(f"{path}: {n} endpoints")

def cmd_ops(args):
    for path in args.spec:
        spec = _load_yaml(path)
        ops = collect_operation_ids(spec)
        missing = CANONICAL_OPS - ops
        print(f"{path}: found {len(ops)} operationIds")
        if ops:
            print("  operationIds:", ", ".join(sorted(ops)))
        if missing:
            print("  ⚠️  Missing canonical ops:", ", ".join(sorted(missing)))
        else:
            print("  ✅ Canonical operationIds present")

def _http_get(url: str, params: Dict[str, Any]) -> Tuple[int, str]:
    try:
        import requests  # type: ignore
    except Exception:
        print("The 'requests' package is required for live tests. Install with: pip install requests", file=sys.stderr)
        raise
    r = requests.get(url, params=params, timeout=20)
    ctype = r.headers.get("content-type", "")
    return r.status_code, f"{url}?{r.request.body or r.request.url.split('?',1)[1] if '?' in r.request.url else ''}  ->  {r.status_code} ({ctype})"

def cmd_live_portal(args):
    url = "https://www.arcgis.com/sharing/rest/search"
    params = {"q": "type:Feature Service AND owner:*", "num": 1, "start": 1, "f": "json"}
    code, msg = _http_get(url, params)
    print(msg)
    print("PASS" if code == 200 else "FAIL")
    sys.exit(0 if code == 200 else 2)

def cmd_live_services(args):
    base = "https://services1.arcgis.com"
    path = "/QWdNfRs7lkPq4g4Q/arcgis/rest/services/Private_Well_Testing_Act_Summary_Results_by_County_for_New_Jersey/FeatureServer/65/query"
    params = {"f":"json","where":"1=1","outFields":"*","returnGeometry":"false","resultRecordCount":1}
    code, msg = _http_get(base + path, params)
    print(msg)
    print("PASS" if code == 200 else "FAIL")
    sys.exit(0 if code == 200 else 2)

def main():
    ap = argparse.ArgumentParser(description="Validate OpenAPI specs and perform optional live tests.")
    sub = ap.add_subparsers(required=True)

    sp = sub.add_parser("lint", help="Basic structure validation")
    sp.add_argument("--spec", action="append", required=True, help="Path to OpenAPI file (yaml/json). Repeatable.")
    sp.set_defaults(func=cmd_lint)

    sp2 = sub.add_parser("count", help="Count endpoints in spec(s)")
    sp2.add_argument("--spec", action="append", required=True)
    sp2.set_defaults(func=cmd_count)

    sp3 = sub.add_parser("ops", help="List operationIds and check canonical ones")
    sp3.add_argument("--spec", action="append", required=True)
    sp3.set_defaults(func=cmd_ops)

    sp4 = sub.add_parser("live-portal", help="Run a live GET against ArcGIS Portal /search")
    sp4.set_defaults(func=cmd_live_portal)

    sp5 = sub.add_parser("live-services", help="Run a live FeatureServer query (NJDEP example)")
    sp5.set_defaults(func=cmd_live_services)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

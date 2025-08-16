#!/usr/bin/env python3
"""
Enhanced HAR File Analyzer for API Discovery
--------------------------------------------
- Filters out static assets and focuses on API-like traffic
- Redacts secrets in headers and query params
- Clusters requests into endpoint patterns
- (ArcGIS mode) Generates *curated* OpenAPI specs for:
    - ArcGIS Portal:    portal.openapi.yaml
    - ArcGIS Services:  services.openapi.yaml
- Can also emit a combined, generic OpenAPI skeleton
- Produces a human-readable Markdown report

Usage examples:
  python har_analyzer.py capture_sanitized.har \
    --arcgis --out-portal portal.openapi.yaml \
    --out-services services.openapi.yaml \
    --out-report HAR_REPORT.md

  python har_analyzer.py capture_sanitized.har --out-skeleton api-skeleton.yaml

Requirements:
  pip install pyyaml

Author: Auto-generated helper
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple, Optional
from urllib.parse import urlparse

# --------------------------
# Redaction & utility helpers
# --------------------------

REDACT_KEYS = {
    "authorization", "cookie", "x-csrf-token", "x-xsrf-token",
    "token", "apikey", "api_key", "key", "access_token", "refresh_token"
}

STATIC_PATH_HINTS = (
    "/assets/", "/static/", "/scripts/", "/images/", "/css/", "/js/",
    "/fonts/", "/favicon", "/calcite-components/", "/opendata-ui/",
    "/dbcdn/"
)

def redact_value(name: str, value: str) -> str:
    if name is None:
        return value
    if any(k in name.lower() for k in REDACT_KEYS):
        return "***REDACTED***"
    # If looks like a JWT or long token-like string, redact
    if re.match(r"^[A-Za-z0-9-_]{20,}\.[A-Za-z0-9-_]{10,}\.[A-Za-z0-9-_]{10,}$", value or ""):
        return "***REDACTED***"
    if len(value or "") > 256:
        return value[:128] + "...(truncated)"  # keep report readable
    return value

def safe_get(d: Dict[str, Any], *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def load_har(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading HAR file {filepath}: {e}")
        sys.exit(1)

# --------------------------
# Candidate extraction
# --------------------------

def is_static_asset(url: str, response_mime: str) -> bool:
    if response_mime:
        if any(x in response_mime.lower() for x in [
            "text/html", "image/", "font/", "javascript", "css"
        ]):
            return True
    if any(hint in url for hint in STATIC_PATH_HINTS):
        return True
    return False

def looks_like_api(url: str) -> bool:
    # Broad heuristics for API-like URLs
    return bool(re.search(r"/(api|rest|graphql|FeatureServer|MapServer|sharing)/", url, re.I))

def extract_api_candidates(har: Dict[str, Any],
                           only_json: bool = False,
                           exclude_static: bool = True,
                           host_allowlist: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    entries = safe_get(har, "log", "entries", default=[])
    out = []

    for e in entries:
        req = e.get("request", {})
        res = e.get("response", {})
        url = req.get("url", "")
        method = req.get("method", "GET").upper()
        mime = safe_get(res, "content", "mimeType", default="")
        status = res.get("status", 0)

        if host_allowlist:
            host = urlparse(url).netloc
            if not any(host.endswith(h) or host == h for h in host_allowlist):
                continue

        if exclude_static and is_static_asset(url, mime):
            continue

        if only_json and "json" not in (mime or "").lower():
            continue

        if not looks_like_api(url) and method == "GET" and status in (301, 302, 303, 307, 308, 200) and not only_json:
            # Ignore likely non-API GETs unless we are specifically targeting JSON
            continue

        headers = {h["name"]: redact_value(h["name"], h.get("value", "")) for h in req.get("headers", [])}
        qparams = {q["name"]: redact_value(q["name"], q.get("value", "")) for q in req.get("queryString", [])}
        body_text = safe_get(req, "postData", "text", default="")
        body_text = redact_value("postData", body_text or "")

        res_body = safe_get(res, "content", "text", default="")
        res_body = redact_value("response_body", res_body or "")

        out.append({
            "url": url,
            "method": method,
            "status": status,
            "req_headers": headers,
            "query": qparams,
            "request_body": body_text,
            "response_mime": mime or "",
            "response_size": safe_get(res, "content", "size", default=0) or 0,
            "response_body": res_body,
            "time_ms": e.get("time", 0),
        })
    return out

# --------------------------
# Pattern analysis
# --------------------------

def normalize_path_for_patterns(path: str) -> str:
    # Replace numeric segments and GUID-like segments with placeholders
    path = re.sub(r"/\d+(?=/|$)", "/{id}", path)
    path = re.sub(r"/[A-Fa-f0-9]{8,}(?=/|$)", "/{id}", path)
    return path

def analyze_patterns(calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    patterns = defaultdict(list)
    base_urls = Counter()
    for c in calls:
        parsed = urlparse(c["url"])
        base = f"{parsed.scheme}://{parsed.netloc}"
        base_urls[base] += 1
        normalized = normalize_path_for_patterns(parsed.path)
        key = f"{c['method']} {normalized}"
        patterns[key].append(c)
    return {"patterns": dict(patterns), "base_urls": dict(base_urls), "most_common_base": base_urls.most_common(1)[0] if base_urls else None}

# --------------------------
# ArcGIS-specific OpenAPI builders
# --------------------------

def arcgis_build_portal_openapi(calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    # Server must be arcgis.com to bother
    if not any("arcgis.com" in urlparse(c["url"]).netloc for c in calls):
        return None

    portal_paths = {}
    saw_any = False

    # Any call to these endpoints? If yes, add with standard params
    # /sharing/rest/search
    if any("/sharing/rest/search" in urlparse(c["url"]).path for c in calls):
        saw_any = True
        portal_paths["/sharing/rest/search"] = {
            "get": {
                "summary": "Search ArcGIS items",
                "operationId": "searchItems",
                "parameters": [
                    {"in": "query", "name": "q", "schema": {"type": "string"}, "example": "type:Feature Service", "description": "Search query"},
                    {"in": "query", "name": "num", "schema": {"type": "integer"}, "example": 10, "description": "Page size"},
                    {"in": "query", "name": "start", "schema": {"type": "integer"}, "example": 1, "description": "1-based start index"},
                    {"in": "query", "name": "f", "schema": {"type": "string", "enum": ["json"]}, "example": "json"}
                ],
                "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}}
            }
        }

    # /sharing/rest/content/items/{itemId}
    if any("/sharing/rest/content/items/" in urlparse(c["url"]).path and "/data" not in urlparse(c["url"]).path for c in calls):
        saw_any = True
        portal_paths["/sharing/rest/content/items/{itemId}"] = {
            "get": {
                "summary": "Get ArcGIS item metadata",
                "operationId": "getItemMetadata",
                "parameters": [
                    {"in": "path", "name": "itemId", "required": True, "schema": {"type": "string"}},
                    {"in": "query", "name": "f", "schema": {"type": "string", "enum": ["json"]}, "example": "json"}
                ],
                "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}}
            }
        }

    # /sharing/rest/content/items/{itemId}/data
    if any("/sharing/rest/content/items/" in urlparse(c["url"]).path and "/data" in urlparse(c["url"]).path for c in calls):
        saw_any = True
        portal_paths["/sharing/rest/content/items/{itemId}/data"] = {
            "get": {
                "summary": "Get ArcGIS item data/config",
                "operationId": "getItemData",
                "parameters": [
                    {"in": "path", "name": "itemId", " " "required": True, "schema": {"type": "string"}},
                    {"in": "query", "name": "f", "schema": {"type": "string", "enum": ["json"]}, "example": "json"}
                ],
                "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}}
            }
        }

    if not saw_any:
        return None

    return {
        "openapi": "3.0.3",
        "info": {"title": "ArcGIS Portal API", "version": "1.0.0", "description": "ArcGIS Portal endpoints inferred from HAR"},
        "servers": [{"url": "https://www.arcgis.com"}],
        "paths": portal_paths,
        "components": {"schemas": {}}
    }

def arcgis_build_services_openapi(calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    # Only consider services*.arcgis.com
    if not any(re.match(r"services\d*\.arcgis\.com$", urlparse(c["url"]).netloc) for c in calls):
        return None

    services_paths: Dict[str, Any] = {}
    saw_any = False

    def ensure_path(p):
        if p not in services_paths:
            services_paths[p] = {}

    # Root service describe
    if any("/FeatureServer" in urlparse(c["url"]).path and not re.search(r"/FeatureServer/\d+", urlparse(c["url"]).path) for c in calls):
        saw_any = True
        p = "/{orgId}/arcgis/rest/services/{servicePath}/FeatureServer"
        ensure_path(p)
        services_paths[p]["get"] = {
            "summary": "Describe feature service (list layers/tables)",
            "operationId": "describeFeatureServer",
            "parameters": [
                {"in": "path", "name": "orgId", "required": True, "schema": {"type": "string"}},
                {"in": "path", "name": "servicePath", "required": True, "schema": {"type": "string"}},
                {"in": "query", "name": "f", "schema": {"type": "string", "enum": ["json"]}, "example": "json"}
            ],
            "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}}
        }

    # Layer describe
    if any(re.search(r"/FeatureServer/\d+($|/)", urlparse(c["url"]).path) and "/query" not in urlparse(c["url"]).path for c in calls):
        saw_any = True
        p = "/{orgId}/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}"
        ensure_path(p)
        services_paths[p]["get"] = {
            "summary": "Describe feature layer",
            "operationId": "describeFeatureLayerGeneric",
            "parameters": [
                {"in": "path", "name": "orgId", "required": True, "schema": {"type": "string"}},
                {"in": "path", "name": "servicePath", "required": True, "schema": {"type": "string"}},
                {"in": "path", "name": "layerId", "required": True, "schema": {"type": "integer"}},
                {"in": "query", "name": "f", "schema": {"type": "string", "enum": ["json"]}, "example": "json"}
            ],
            "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}}
        }

    # Query
    if any("/query" in urlparse(c["url"]).path and "/FeatureServer/" in urlparse(c["url"]).path for c in calls):
        saw_any = True
        p = "/{orgId}/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}/query"
        ensure_path(p)
        services_paths[p]["get"] = {
            "summary": "Query feature layer",
            "operationId": "queryFeatureLayerGeneric",
            "parameters": [
                {"in": "path", "name": "orgId", "required": True, "schema": {"type": "string"}},
                {"in": "path", "name": "servicePath", "required": True, "schema": {"type": "string"}},
                {"in": "path", "name": "layerId", "required": True, "schema": {"type": "integer"}},
                {"in": "query", "name": "f", "schema": {"type": "string", "enum": ["json", "pbf"]}, "example": "json"},
                {"in": "query", "name": "where", "schema": {"type": "string"}, "example": "1=1"},
                {"in": "query", "name": "outFields", "schema": {"type": "string"}, "example": "*"},
                {"in": "query", "name": "returnGeometry", "schema": {"type": "boolean"}, "example": False},
                {"in": "query", "name": "resultRecordCount", "schema": {"type": "integer"}, "example": 5},
            ],
            "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}}
        }

    if not saw_any:
        return None

    # Choose the most common services host to pin the server
    bases = Counter()
    for c in calls:
        n = urlparse(c["url"]).netloc
        if re.match(r"services\d*\.arcgis\.com$", n):
            bases[n] += 1
    server_url = f"https://{(bases.most_common(1)[0][0] if bases else 'services1.arcgis.com')}"

    return {
        "openapi": "3.0.3",
        "info": {"title": "ArcGIS FeatureServer API", "version": "1.0.0", "description": "ArcGIS FeatureServer endpoints inferred from HAR"},
        "servers": [{"url": server_url, "description": "Most frequent services host from HAR"}],
        "paths": services_paths,
        "components": {
            "schemas": {
                "Field": {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}}},
                "Feature": {"type": "object", "properties": {"attributes": {"type": "object"}, "geometry": {"nullable": True}}},
                "FeatureSet": {"type": "object", "properties": {
                    "objectIdFieldName": {"type": "string"},
                    "fields": {"type": "array", "items": {"$ref": "#/components/schemas/Field"}},
                    "features": {"type": "array", "items": {"$ref": "#/components/schemas/Feature"}}
                }}
            }
        }
    }

# --------------------------
# Generic OpenAPI skeleton
# --------------------------

def generic_openapi_skeleton(patterns: Dict[str, List[Dict[str, Any]]], most_common_base: Optional[Tuple[str, int]]) -> Dict[str, Any]:
    base_url = most_common_base[0] if most_common_base else "https://api.example.com"
    spec: Dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Discovered API", "version": "1.0.0", "description": "Generic skeleton derived from HAR"},
        "servers": [{"url": base_url, "description": "Primary base URL from HAR"}],
        "paths": {},
        "components": {"schemas": {}, "securitySchemes": {}}
    }
    for key, calls in patterns.items():
        method, path = key.split(" ", 1)
        if path not in spec["paths"]:
            spec["paths"][path] = {}
        op = {
            "summary": f"{method} {path}",
            "description": f"Observed {len(calls)} calls in HAR",
            "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object"}}}}}
        }
        # Try to harvest a few query params as examples
        sample_q = calls[0].get("query", {})
        if sample_q:
            op["parameters"] = []
            for name, val in list(sample_q.items())[:6]:
                op["parameters"].append({
                    "name": name, "in": "query", "required": False, "schema": {"type": "string"},
                    "example": val, "description": "Discovered from HAR"
                })
        spec["paths"][path][method.lower()] = op
    return spec

# --------------------------
# Reporting
# --------------------------

def write_yaml(path: str, obj: Dict[str, Any]):
    try:
        import yaml
    except ImportError:
        print("❌ Missing dependency: pyyaml. Install with: pip install pyyaml")
        sys.exit(1)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, sort_keys=False, allow_unicode=True)

def write_md_report(path: str, calls: List[Dict[str, Any]], patterns: Dict[str, List[Dict[str, Any]]], base_urls: Dict[str, int]):
    lines = []
    lines.append("# HAR Analysis Report\n")
    lines.append(f"- Total API-like calls: **{len(calls)}**")
    if base_urls:
        top = sorted(base_urls.items(), key=lambda x: x[1], reverse=True)[:5]
        lines.append("- Top base URLs:")
        for b, c in top:
            lines.append(f"  - `{b}` — {c} calls")
    lines.append("\n## Endpoint Patterns\n")
    for key, pcs in sorted(patterns.items(), key=lambda kv: kv[0]):
        statuses = Counter(p["status"] for p in pcs)
        stat_str = ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items()))
        lines.append(f"- `{key}` — {len(pcs)} calls (status: {stat_str})")
    lines.append("\n## Notes\n- Static assets were filtered by default.\n- Sensitive values in headers/params were redacted.\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# --------------------------
# Main
# --------------------------

def main():
    ap = argparse.ArgumentParser(description="Analyze HARs and generate OpenAPI + reports")
    ap.add_argument("har_files", nargs="+", help="One or more HAR paths")
    ap.add_argument("--only-json", action="store_true", help="Keep only responses with JSON mimetype")
    ap.add_argument("--include-host", action="append", help="Only include hosts matching this (can be used multiple times)")
    ap.add_argument("--no-exclude-static", action="store_true", help="Do NOT exclude static assets")
    ap.add_argument("--arcgis", action="store_true", help="Enable ArcGIS-specific heuristics and outputs")
    ap.add_argument("--out-skeleton", help="Write a generic OpenAPI skeleton to this path (YAML)")
    ap.add_argument("--out-portal", help="(ArcGIS) Write portal.openapi.yaml here")
    ap.add_argument("--out-services", help="(ArcGIS) Write services.openapi.yaml here")
    ap.add_argument("--out-report", help="Write Markdown report to this path")
    args = ap.parse_args()

    all_calls: List[Dict[str, Any]] = []
    for hp in args.har_files:
        har = load_har(hp)
        calls = extract_api_candidates(
            har,
            only_json=args.only_json,
            exclude_static=not args.no_exclude_static,
            host_allowlist=args.include_host
        )
        all_calls.extend(calls)

    if not all_calls:
        print("❌ No API-like calls detected with the current filters.")
        sys.exit(2)

    analysis = analyze_patterns(all_calls)
    patterns = analysis["patterns"]
    base_urls = analysis["base_urls"]
    most_common_base = analysis["most_common_base"]

    print("✅ Analyzed calls:", len(all_calls))
    print("✅ Unique endpoint patterns:", len(patterns))
    if most_common_base:
        print(f"✅ Most common base: {most_common_base[0]} ({most_common_base[1]} calls)")

    # Outputs
    if args.out_report:
        write_md_report(args.out_report, all_calls, patterns, base_urls)
        print(f"📝 Report written to: {args.out_report}")

    if args.out_skeleton:
        spec = generic_openapi_skeleton(patterns, most_common_base)
        write_yaml(args.out_skeleton, spec)
        print(f"🧩 Generic OpenAPI skeleton written to: {args.out_skeleton}")

    if args.arcgis:
        portal_spec = arcgis_build_portal_openapi(all_calls)
        services_spec = arcgis_build_services_openapi(all_calls)

        if args.out_portal and portal_spec:
            write_yaml(args.out_portal, portal_spec)
            print(f"🌐 Portal OpenAPI written to: {args.out_portal}")
        elif args.out_portal:
            print("ℹ️ No portal endpoints detected; skipping portal.openapi.yaml")

        if args.out_services and services_spec:
            write_yaml(args.out_services, services_spec)
            print(f"🗂️ Services OpenAPI written to: {args.out_services}")
        elif args.out_services:
            print("ℹ️ No services endpoints detected; skipping services.openapi.yaml")

if __name__ == "__main__":
    main()

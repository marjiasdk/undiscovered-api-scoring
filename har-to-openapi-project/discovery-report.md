``# HPSC Notifiable Disease – ArcGIS API Discovery (from HAR)

**Project goal:** Reverse‑engineer and document the public ArcGIS endpoints used by `notifiabledisease.hpsc.ie`, and validate them with an executable OpenAPI 3.0+ specification.

---

## 1) Sources & Scope

- **Primary evidence:** Sanitized HAR captures taken while loading the HPSC dashboards.
- **Observed platforms:**
  - **ArcGIS Portal** (`www.arcgis.com`) — search & item metadata.
  - **ArcGIS Hosted Feature Services** (`services{1,2,3,7}.arcgis.com`) — FeatureServer layer and query endpoints.
- **Deliverable spec:** `openapi.yaml` titled **“HPSC Notifiable Disease – ArcGIS API”** (OpenAPI 3.0.3).

> The spec intentionally includes both **fixed‑org** HPSC endpoints (org id `dQsP3byyKkTT53Ep` on `services3.arcgis.com`) and **generic** endpoints that work for any ArcGIS Online org (`{orgId}`), because Portal search frequently returns datasets hosted under different orgs/hosts (e.g., NJDEP on `services1.arcgis.com`).

---

## 2) Methodology (How the API was discovered)

1. **Capture HAR while using the site**
   - Open Chrome DevTools → Network → Preserve log → Export HAR.
   - Filter by “arcgis.com” to isolate ArcGIS calls.

2. **Identify stable REST patterns**
   - **Portal search & content:**
     - `/sharing/rest/search`
     - `/sharing/rest/content/items/{itemId}`
     - `/sharing/rest/content/items/{itemId}/data`
   - **Feature services (data):**
     - `/{orgId}/arcgis/rest/services/{servicePath}/FeatureServer`
     - `/{orgId}/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}`
     - `/{orgId}/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}/query`

3. **Extract required params from requests**
   - Portal: `q`, `num`, `start`, `f=json`.
   - FeatureServer: path params `orgId`, `servicePath`, `layerId`; query params `f=json`, `where`, `outFields`, `returnGeometry`, `resultRecordCount`, etc.

4. **Model endpoints in OpenAPI**
   - Define **servers** for both Portal and FeatureServer hosts.
   - Add **fixed‑org** HPSC endpoints (handy for direct queries).
   - Add **generic** endpoints parameterized by `{orgId}` to support results discovered via search.
   - Provide light **schemas** for `ArcgisItem` and `FeatureSet` to keep the spec implementable, with examples for quick testing.

5. **Validate by calling the endpoints via `arazzo_runner`**
   - Run sample operations and confirm 200 responses with realistic payloads.
   - Adjust host selection behavior when the runner prefers the first `servers:` entry.

---

## 3) Endpoint Inventory (from the OpenAPI)

### 3.1 Portal (metadata) – `https://www.arcgis.com`

- **`GET /sharing/rest/search`** (`operationId: searchItems`)  
  Search ArcGIS items. Parameters: `q`, `num`, `start`, `f=json`.

- **`GET /sharing/rest/content/items/{itemId}`** (`getItemMetadata`)  
  Fetches item metadata (title, url, tags, etc.).

- **`GET /sharing/rest/content/items/{itemId}/data`** (`getItemData`)  
  Fetches item “data” JSON (e.g., dashboard config).

### 3.2 Feature Services (data) – `https://services*.arcgis.com`

- **Fixed org (HPSC on `services3`)**
  - `GET /dQsP3byyKkTT53Ep/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}` (`describeFeatureLayer`)
  - `GET /dQsP3byyKkTT53Ep/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}/query` (`queryFeatureLayer`)

- **Generic (any org)**
  - `GET /{orgId}/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}` (`describeFeatureLayerGeneric`)
  - `GET /{orgId}/arcgis/rest/services/{servicePath}/FeatureServer/{layerId}/query` (`queryFeatureLayerGeneric`)

> **Host routing note:** Some runners (incl. `arazzo_runner`) apply the **first** top‑level server to *every* path, ignoring per‑path servers. To avoid mis‑routing (e.g., sending FeatureServer calls to `www.arcgis.com`), we also use a **separate services spec** pinned to `services1.arcgis.com` when querying NJDEP data discovered via Portal search.

---

## 4) Validation (evidence the spec works)

Below are the exact commands that produced real responses during validation.

### 4.1 Portal search working
```bash
python -m arazzo_runner execute-operation \
  --openapi-path portal.openapi.yaml \
  --operation-id searchItems \
  --inputs '{"q":"test","num":10,"start":1,"f":"json"}'
```
**Observed:** HTTP 200 with a `results` array of ArcGIS items (Feature Services, etc.).

### 4.2 Feature service discovery → query (generic org)

**Describe service (list layers):**
```bash
python -m arazzo_runner execute-operation \
  --openapi-path services.openapi.yaml \
  --operation-id describeFeatureServer \
  --inputs '{
    "orgId": "QWdNfRs7lkPq4g4Q",
    "servicePath": "Private_Well_Testing_Act_Summary_Results_by_County_for_New_Jersey",
    "f": "json"
  }'
```
**Observed:** HTTP 200 with `layers: [{ "id": 65, "name": "...By County..." }]`.

**Query the discovered layer (id 65):**
```bash
python -m arazzo_runner execute-operation \
  --openapi-path services.openapi.yaml \
  --operation-id queryFeatureLayerGeneric \
  --inputs '{
    "orgId":"QWdNfRs7lkPq4g4Q",
    "servicePath":"Private_Well_Testing_Act_Summary_Results_by_County_for_New_Jersey",
    "layerId":65,
    "f":"json",
    "where":"1=1",
    "outFields":"*",
    "returnGeometry":false,
    "resultRecordCount":5
  }'
```
**Observed:** HTTP 200 with real features (e.g., `COUNTY`, `REGION`, `PFAS`, `IRON`, etc.).

---

## 5) Common Pitfalls & Troubleshooting

- **404 HTML from `www.arcgis.com` while querying FeatureServer**  
  Your runner likely used the first `servers` entry globally. Use a **separate `services.openapi.yaml`** pinned to the correct host (`services1.arcgis.com` for NJDEP, `services3.arcgis.com` for HPSC).

- **“Invalid URL” (400) on FeatureServer paths**  
  Usually caused by wrong host or a missing/typo’d `servicePath`. Copy it from the item’s `url` property exactly.

- **“The requested layer (layerId: 0) was not found.”**  
  Many services start at `layerId = 1` or higher. Call the service root (`/FeatureServer`) to list `layers[]` and pick the right id.

- **Shell quoting in zsh**  
  When embedding single quotes inside JSON (e.g., `COUNTY='MORRIS'`), escape as `'\''` or put your inputs into a separate `.json` file and use `--inputs @file.json`.

- **Exceeded transfer limit**  
  The response may include `"exceededTransferLimit": true`. Use paging with `resultOffset` + `resultRecordCount` to iterate results.

---

## 6) How to interpret ArcGIS results

- **Portal search results** include `id`, `title`, `type`, and crucially a `url` pointing to the service:  
  `https://servicesX.arcgis.com/{orgId}/arcgis/rest/services/{servicePath}/FeatureServer`

- **FeatureServer query responses** return:
  - `fields[]`: schema (names, types).
  - `features[].attributes`: row values.
  - `geometry` only when `returnGeometry=true`.
  - Optional stats when using `groupByFieldsForStatistics` + `outStatistics`.

> Many of the NJDEP “measurement” columns are **strings** like `"16.1%, 13434 wells sampled"`. Treat them as display fields, not numeric values.

---

## 7) Security & Hygiene

- **Sanitize HAR** before sharing: remove cookies, tokens, referer headers, and any user identifiers.
- All endpoints exercised here are **public** (no auth required), but treat API keys or tokens in other contexts as secrets.
- Respect item **licenseInfo** and **terms** when redistributing data.

---

## 8) What’s next (to reach higher deliverable tiers)

- **Enhanced**: Add ≥5 endpoints total
  - e.g., `orderByFields`, `resultOffset`, `groupByFieldsForStatistics`, `outStatistics`, and an **export** endpoint if available.
- **Professional**:
  - Flesh out **response schemas** (`ArcgisItem`, `FeatureSet`) with full field definitions.
  - Build a small **HAR → OpenAPI** extraction script.
  - Write a short **security best‑practices** doc (rate limits, caching, PII, licensing).
  - Contribute the spec to the **Jentic Public APIs** repo.

---

## 9) Appendix: Mapping from HAR → OpenAPI (example)

| HAR request (method & path) | Purpose | OpenAPI path & operationId |
|---|---|---|
| `GET https://www.arcgis.com/sharing/rest/search?q=...&f=json` | Search items | `/sharing/rest/search` → `searchItems` |
| `GET https://www.arcgis.com/sharing/rest/content/items/{itemId}?f=json` | Item metadata | `/sharing/rest/content/items/{itemId}` → `getItemMetadata` |
| `GET https://services3.arcgis.com/dQsP.../arcgis/rest/services/IDHUB_SummaryMaster_L/FeatureServer/0?f=json` | Layer describe | `/dQsP3.../FeatureServer/{layerId}` → `describeFeatureLayer` |
| `GET https://services1.arcgis.com/QWdN.../arcgis/rest/services/Private_Well_Testing_Act_.../FeatureServer/65/query?f=json&where=1%3D1&outFields=*` | Data query | `/{orgId}/.../FeatureServer/{layerId}/query` → `queryFeatureLayerGeneric` |

---

**Maintainer:** _Your Name_  
**Spec file:** `openapi.yaml` (Portal + HPSC fixed + Generic FeatureServer)  
**Companion file for querying services:** `services.openapi.yaml` (pinned to `services1` for NJDEP)
``
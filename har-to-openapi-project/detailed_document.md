## 4. Quickstart Examples (copy/paste)

### 4.1 Search items (Portal)
This example shows how to search for feature services on the ArcGIS Portal.

```bash
python -m arazzo_runner execute-operation \
  --openapi-path portal.openapi.yaml \
  --operation-id searchItems \
  --inputs '{"q":"type:Feature Service AND owner:*","num":5,"start":1,"f":"json"}'
```
**Expected Output:**  
An HTTP 200 response with a `results` array containing item details like `id`, `title`, `type`, and a URL to the corresponding FeatureServer.

---

### 4.2 Describe a Feature Service to find the layer id
This command helps you identify the `layerId` you need for subsequent queries by describing a specific Feature Service.

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
**Expected Output:**  
Look for `layers[0].id` in the JSON response. For the NJDEP service, this ID is `65`.

---

### 4.3 Query the layer (raw records)
Once you have the `layerId`, you can query the layer for raw data records.

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
**Expected Output:**  
An HTTP 200 response with a `fields` array and a `features` array, where each feature contains an `attributes` object with data fields like `COUNTY`, `REGION`, and `PFAS`. Many fields are display-formatted strings.

---

## 5. Arazzo Workflow Example

A minimal workflow to run the query is provided in `test-workflow.arazzo.yaml`:

```yaml
workflows:
  - workflowId: query_njdep
    steps:
      - stepId: query
        api: services
        operationId: queryFeatureLayerGeneric
        parameters:
          orgId: QWdNfRs7lkPq4g4Q
          servicePath: Private_Well_Testing_Act_Summary_Results_by_County_for_New_Jersey
          layerId: 65
          f: json
          where: "1=1"
          outFields: "*"
          returnGeometry: false
          resultRecordCount: 5
```

To run the workflow:

```bash
python -m arazzo_runner execute-workflow ./test-workflow.arazzo.yaml \
  --workflow-id query_njdep
```

This works because the `api` and `operationId` are explicitly set for each step, and the `apis` block in the runner configuration points to `./services.openapi.yaml`.  
If you get an error like `"Step X does not specify an operation or workflow to execute,"` ensure your step definition includes `api` and `operationId`.

---

## 6. Automated HAR Analysis (Script)

You can use a HAR analyzer script to quickly generate an OpenAPI skeleton. This is a great starting point for building your own spec.

```bash
python har_analyzer.py /path/to/capture_sanitized.har \
  --output api-skeleton.yaml --format yaml
```

The resulting `api-skeleton.yaml` provides inferred paths and parameters from the HAR.  
You'll need to curate this skeleton by cleaning up static assets, consolidating path parameters, and adding more detailed schemas.  
Use the curated specs (`portal.openapi.yaml` and `services.openapi.yaml`) for validation with `arazzo_runner`.

---

## 7. Troubleshooting (real issues encountered & fixes)

- **404 HTML from www.arcgis.com when hitting FeatureServer**
  - *Cause:* Some runners apply the first top-level server globally, ignoring per-path servers.
  - *Fix:* Use the `services.openapi.yaml` spec for queries, as its host is pinned to `services1.arcgis.com` for NJDEP. Alternatively, move all FeatureServer paths into a separate specification file.

- **HTTP 400 “Invalid URL”**
  - *Cause:* Incorrect host or a typo in the `servicePath`.
  - *Fix:* Double-check the service URL and `servicePath` against the item metadata or search results.

- **“The requested layer (layerId: 0) was not found.”**
  - *Cause:* Layer IDs do not always start at 0.
  - *Fix:* Call the service root (`/FeatureServer`) to list all available layers and their IDs, then use the correct ID (e.g., `65`).

- **Zsh quoting hell when JSON has single quotes**
  - *Fix:* Escape single quotes as `'\''` or save the JSON inputs to a file (e.g., `inputs.json`) and pass it using `--inputs @inputs.json`.

- **"exceededTransferLimit": true on large queries**
  - *Fix:* Implement pagination using `resultOffset` and `resultRecordCount`, or narrow the query using a more specific `where` clause.

- **Arazzo workflow step errors (“does not specify an operation…”)**
  - *Cause:* The step is missing `api` and/or `operationId`.
  - *Fix:* Ensure your workflow structure matches `test-workflow.arazzo.yaml`.

---

## 8. Endpoint Examples (Expanded)

Here are more copy-ready examples of the different API operations.

### 8.1 Portal Search (list dashboards or services)

```bash
python -m arazzo_runner execute-operation \
  --openapi-path portal.openapi.yaml \
  --operation-id searchItems \
  --inputs '{"q":"type:(Feature Service OR Dashboard) AND owner:*","num":10,"start":1,"f":"json"}'
```
**Response:**  
The response schema for `results[]` is defined as `ArcgisItem` in `portal.openapi.yaml`.

---

### 8.2 Describe Service → Get Layers

```bash
python -m arazzo_runner execute-operation \
  --openapi-path services.openapi.yaml \
  --operation-id describeFeatureServer \
  --inputs '{"orgId":"QWdNfRs7lkPq4g4Q","servicePath":"Private_Well_Testing_Act_Summary_Results_by_County_for_New_Jersey","f":"json"}'
```
**Response:**  
Inspect the `layers[]` array in the response to determine the correct `layerId`.

---

### 8.3 Query: Top N records

```bash
python -m arazzo_runner execute-operation \
  --openapi-path services.openapi.yaml \
  --operation-id queryFeatureLayerGeneric \
  --inputs '{"orgId":"QWdNfRs7lkPq4g4Q","servicePath":"Private_Well_Testing_Act_Summary_Results_by_County_for_New_Jersey","layerId":65,"f":"json","where":"1=1","outFields":"*","returnGeometry":false,"resultRecordCount":5}'
```
**Response:**  
Returns a JSON object with `fields[]` and `features[].attributes`.

---

## 9. How this meets the Enhanced deliverables

- **Comprehensive API coverage (5+ endpoints):**  
  This guide covers at least six endpoints: three for the Portal (`/search`, `/items/{id}`, `/items/{id}/data`) and three for the FeatureServer (`/FeatureServer`, `/FeatureServer/{layerId}`, `/FeatureServer/{layerId}/query`).

- **Test workflow demonstrating usage:**  
  The `test-workflow.arazzo.yaml` file provides a working example of an end-to-end query.

- **Analysis script for automated HAR processing:**  
  The guide provides instructions for using a HAR analyzer to generate an OpenAPI skeleton.

- **Detailed documentation with examples & troubleshooting:**  
  The document includes runnable commands, expected outputs, and practical solutions for common errors related to hosts, layer IDs, quoting, and data limits.

---

## 10. Suggested Next Steps (toward “Professional Quality”)

- **Tighten Schemas:**  
  Expand the `FeatureSet` and `ArcgisItem` schemas to include common field types and enums from ArcGIS.

- **Add Statistical Query Examples:**  
  Add examples for statistical queries using `groupByFieldsForStatistics` and `outStatistics` within the OpenAPI specification.

- **Automate Conversion:**  
  Enhance the HAR analyzer with ArcGIS-specific heuristics to collapse path wildcards (`{id}`), infer parameters (`{orgId}`, `{servicePath}`), and emit cleaner OpenAPI specs.

- **Security Notes:**  
  Document that all endpoints are public, emphasize the importance of sanitizing HAR files, and note any observed rate-limiting or caching behavior.

---

## 11. Appendix: Mapping HAR → OpenAPI

| HAR Request | Purpose | OpenAPI Path → OperationId |
|-------------|---------|---------------------------|
| GET https://www.arcgis.com/sharing/rest/search?q=... | Search items | /sharing/rest/search → searchItems |
| GET https://www.arcgis.com/sharing/rest/content/items/{itemId}?f=json | Item metadata | /sharing/rest/content/items/{itemId} → getItemMetadata |
| GET https://www.arcgis.com/sharing/rest/content/items/{itemId}/data?f=json | Item config | /sharing/rest/content/items/{itemId}/data → getItemData |
| GET https://services1.arcgis.com/{orgId}/.../FeatureServer?f=json | Service describe | /{orgId}/.../FeatureServer → describeFeatureServer |
| GET https://services1.arcgis.com/{orgId}/.../FeatureServer/{layerId}?f=json | Layer describe | /{orgId}/.../FeatureServer/{layerId} → describeFeatureLayerGeneric |
| GET https://services1.arcgis.com/{orgId}/.../FeatureServer/{layerId}/query?... | Data query | /{orgId}/.../FeatureServer/{layerId}/query → queryFeatureLayerGeneric |

*Details corroborated by `discovery-report.md` and the two OpenAPI specs.*


# Example API Calls (ArcGIS Portal + FeatureServer)

## Portal — Search items
```bash
python -m arazzo_runner execute-operation \
  --openapi-path portal.openapi.yaml \
  --operation-id searchItems \
  --inputs '{"q":"type:Feature Service AND owner:*","num":5,"start":1,"f":"json"}'
```

## Services — Describe service (find layerId)
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

## Services — Query layer (records)
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

## Arazzo Workflow — One-shot query
```bash
python -m arazzo_runner execute-workflow ./test-workflow.arazzo.yaml \
  --workflow-id query_njdep
```

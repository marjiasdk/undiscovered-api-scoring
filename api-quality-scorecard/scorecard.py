"""
Scorecard engine for analyzing OpenAPI specifications.

Implements scoring for:
- Documentation Quality
- Schema Completeness
- Agent Usability
- Error Handling
- Authentication
"""

from typing import Dict, Any, List


def score_documentation_quality(spec: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    recommendations: List[str] = []
    total_checks = 0
    passed = 0

    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue

        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue

            # Operation description
            total_checks += 1
            if "description" in operation or "summary" in operation:
                passed += 1
            else:
                issues.append(f"Operation {method.upper()} {path} missing description")
                recommendations.append("Add clear operation descriptions or summaries.")

            # Parameters
            for param in operation.get("parameters", []):
                total_checks += 1
                if "description" in param:
                    passed += 1
                else:
                    pname = param.get("name")
                    issues.append(
                        f"Parameter '{pname}' in {method.upper()} {path} missing description"
                    )
                    recommendations.append(
                        f"Add description and example for parameter '{pname}'."
                    )

            # Responses
            for status, response in operation.get("responses", {}).items():
                total_checks += 1
                if isinstance(response, dict) and "description" in response:
                    passed += 1
                else:
                    issues.append(
                        f"Response {status} in {method.upper()} {path} missing description"
                    )
                    recommendations.append(
                        f"Document response {status} in {method.upper()} {path} with a description."
                    )

    score = int((passed / total_checks) * 100) if total_checks else 0
    return {"score": score, "issues": issues, "recommendations": recommendations}


def score_schema_completeness(spec: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    recommendations: List[str] = []
    total_checks, passed = 0, 0

    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue

            # Request bodies
            request_body = operation.get("requestBody", {})
            if request_body:
                for content in request_body.get("content", {}).values():
                    total_checks += 1
                    if "schema" in content:
                        passed += 1
                    else:
                        issues.append(
                            f"{method.upper()} {path} missing request body schema"
                        )
                        recommendations.append(
                            f"Define request body schema for {method.upper()} {path}."
                        )

            # Responses
            for status, response in operation.get("responses", {}).items():
                if not isinstance(response, dict):
                    continue
                for content in response.get("content", {}).values():
                    total_checks += 1
                    if "schema" in content:
                        passed += 1
                    else:
                        issues.append(
                            f"Response {status} in {method.upper()} {path} missing schema"
                        )
                        recommendations.append(
                            f"Add schema for response {status} in {method.upper()} {path}."
                        )

            # Parameters
            for param in operation.get("parameters", []):
                schema = param.get("schema", {})
                total_checks += 1
                if "type" in schema:
                    passed += 1
                else:
                    pname = param.get("name")
                    issues.append(
                        f"Parameter '{pname}' in {method.upper()} {path} missing type"
                    )
                    recommendations.append(f"Specify parameter type for '{pname}'.")

    # Component schemas
    for schema_name, schema_def in (
        spec.get("components", {}).get("schemas", {}).items()
    ):
        required_fields = schema_def.get("required", [])
        props = schema_def.get("properties", {})
        total_checks += 1
        if required_fields and props:
            passed += 1
        else:
            issues.append(
                f"Schema '{schema_name}' missing required fields or properties"
            )
            recommendations.append(
                f"Add required fields and properties to schema '{schema_name}'."
            )

    score = int((passed / total_checks) * 100) if total_checks else 0
    return {"score": score, "issues": issues, "recommendations": recommendations}


def score_agent_usability(spec):
    issues, recommendations = [], []
    total_checks, passed = 0, 0

    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue

            # OperationId
            total_checks += 1
            op_id = operation.get("operationId")
            if not op_id:
                issues.append(f"Operation {method.upper()} {path} missing operationId")
                recommendations.append(
                    f"Add a descriptive operationId for {method.upper()} {path}."
                )
            elif len(op_id) < 5 or op_id.lower().startswith("op"):
                issues.append(
                    f"OperationId '{op_id}' for {method.upper()} {path} is too generic"
                )
                recommendations.append(
                    f"Use a descriptive operationId instead of '{op_id}'."
                )
            else:
                passed += 1

            # Tags
            total_checks += 1
            if not operation.get("tags"):
                issues.append(f"{method.upper()} {path} missing tags")
                recommendations.append(
                    f"Tag {method.upper()} {path} for better discoverability."
                )
            else:
                passed += 1

            # Descriptions
            if "description" not in operation:
                issues.append(
                    f"{method.upper()} {path} missing description for discoverability"
                )
                recommendations.append(
                    f"Provide detailed description for {method.upper()} {path}."
                )

            # Parameters clarity
            for param in operation.get("parameters", []):
                name = param.get("name", "")
                total_checks += 1
                if len(name) <= 1:
                    issues.append(
                        f"Parameter '{name}' in {method.upper()} {path} too short, unclear"
                    )
                    recommendations.append(
                        f"Use more descriptive parameter names instead of '{name}'."
                    )
                else:
                    passed += 1

            # Complexity: number of params
            total_checks += 1
            if len(operation.get("parameters", [])) > 5:
                issues.append(
                    f"{method.upper()} {path} has too many parameters ({len(operation['parameters'])})"
                )
                recommendations.append(
                    f"Reduce number of parameters in {method.upper()} {path} for simplicity."
                )
            else:
                passed += 1

    score = int((passed / total_checks) * 100) if total_checks else 0
    return {"score": score, "issues": issues, "recommendations": recommendations}


def score_error_handling(spec):
    issues, recommendations = [], []
    total_checks, passed = 0, 0

    error_schema = spec.get("components", {}).get("schemas", {}).get("Error")
    total_checks += 1
    if not error_schema:
        issues.append("No standard 'Error' schema defined in components")
        recommendations.append(
            "Define a standard 'Error' schema with fields like 'error' and 'message'."
        )
    else:
        required_fields = {"message", "error"}
        props = set(error_schema.get("properties", {}).keys())
        if not required_fields.issubset(props):
            issues.append("Error schema missing required fields: message, error")
            recommendations.append(
                "Ensure 'Error' schema includes 'error' and 'message' fields."
            )
        else:
            passed += 1

    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses", {})
            has_4xx = any(code.startswith("4") for code in responses.keys())
            has_5xx = any(code.startswith("5") for code in responses.keys())

            total_checks += 2
            if not has_4xx:
                issues.append(f"{method.upper()} {path} missing 4xx error response")
                recommendations.append(
                    f"Add 4xx error response for {method.upper()} {path}."
                )
            else:
                passed += 1

            if not has_5xx:
                issues.append(f"{method.upper()} {path} missing 5xx error response")
                recommendations.append(
                    f"Add 5xx error response for {method.upper()} {path}."
                )
            else:
                passed += 1

            for code, resp in responses.items():
                if code.startswith(("4", "5")):
                    total_checks += 1
                    if "description" not in resp:
                        issues.append(
                            f"Error response {code} in {method.upper()} {path} missing description"
                        )
                        recommendations.append(
                            f"Document error response {code} in {method.upper()} {path} with description."
                        )
                    else:
                        passed += 1

    score = int((passed / total_checks) * 100) if total_checks else 0
    return {"score": score, "issues": issues, "recommendations": recommendations}


def score_authentication(spec):
    score, issues, recommendations = 100, [], []

    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    if not security_schemes:
        issues.append("No securitySchemes defined in components")
        recommendations.append(
            "Define authentication schemes in components.securitySchemes."
        )
        score -= 30
    else:
        for scheme_name, scheme in security_schemes.items():
            stype = scheme.get("type")
            if not stype:
                issues.append(f"Security scheme '{scheme_name}' missing type")
                recommendations.append(
                    f"Define a type for security scheme '{scheme_name}'."
                )
                score -= 10
            if stype in ["http", "apiKey"] and not scheme.get("description"):
                issues.append(f"Security scheme '{scheme_name}' missing description")
                recommendations.append(
                    f"Add description for '{scheme_name}' auth scheme."
                )
                score -= 5
            if stype == "oauth2":
                flows = scheme.get("flows", {})
                if not flows:
                    issues.append(f"OAuth2 scheme '{scheme_name}' missing flows")
                    recommendations.append(
                        f"Define OAuth2 flows and scopes for '{scheme_name}'."
                    )
                    score -= 15
                else:
                    for flow, cfg in flows.items():
                        if not cfg.get("scopes"):
                            issues.append(
                                f"OAuth2 scheme '{scheme_name}' flow '{flow}' missing scopes"
                            )
                            recommendations.append(
                                f"Add scopes to OAuth2 flow '{flow}' in '{scheme_name}'."
                            )
                            score -= 10

    if "security" not in spec:
        issues.append("No top-level security requirement defined")
        recommendations.append("Define a global security requirement in the root spec.")
        score -= 10

    if "auth" not in (spec.get("info", {}).get("description", "")).lower():
        issues.append("API documentation lacks authentication usage examples")
        recommendations.append("Add authentication usage examples in API description.")
        score -= 5

    score = max(0, min(100, score))
    return {"score": score, "issues": issues, "recommendations": recommendations}


def run_scorecard(spec):
    results = {
        "documentation_quality": score_documentation_quality(spec),
        "schema_completeness": score_schema_completeness(spec),
        "agent_usability": score_agent_usability(spec),
        "error_handling": score_error_handling(spec),
        "authentication": score_authentication(spec),
    }
    scores = [v["score"] for v in results.values()]
    results["overall_score"] = sum(scores) // len(scores) if scores else 0
    return results

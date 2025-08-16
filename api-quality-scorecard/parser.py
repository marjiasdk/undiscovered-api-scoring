import json
import yaml
from pathlib import Path


class OpenAPIParser:
    """
    Parser for OpenAPI 3.x specifications.

    Responsibilities:
    - Load OpenAPI specs from YAML or JSON files.
    - Validate the presence of required fields.
    - Extract key components (version, info, paths, schemas, security).
    """

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.spec = None

    def load_spec(self) -> dict:
        """
        Load the OpenAPI spec from YAML or JSON file.

        Returns:
            dict: Parsed specification as a Python dictionary.
        Raises:
            ValueError: If file type is not supported or parsing fails.
        """
        if not self.filepath.exists():
            raise FileNotFoundError(f"Spec file not found: {self.filepath}")

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                if self.filepath.suffix.lower() == ".json":
                    self.spec = json.load(f)
                else:
                    # default: treat as YAML
                    self.spec = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to load spec: {e}")

        if not isinstance(self.spec, dict):
            raise ValueError("Spec is not a valid JSON/YAML object")

        return self.spec

    def validate(self) -> bool:
        """
        Validate the loaded spec for basic OpenAPI requirements.

        Returns:
            bool: True if validation passes.
        Raises:
            ValueError: If validation fails.
        """
        if not self.spec:
            raise ValueError("Spec not loaded. Call load_spec() first.")

        # Required top-level fields
        if "openapi" not in self.spec:
            raise ValueError("Missing required field: 'openapi'")

        if not str(self.spec["openapi"]).startswith("3."):
            raise ValueError(
                f"Unsupported OpenAPI version: {self.spec['openapi']}. "
                "Only 3.x is supported."
            )

        if "info" not in self.spec:
            raise ValueError("Missing required field: 'info'")

        if "title" not in self.spec["info"] or "version" not in self.spec["info"]:
            raise ValueError("Missing required 'info.title' or 'info.version'")

        if "paths" not in self.spec:
            raise ValueError("Missing required field: 'paths'")

        return True

    def extract_components(self) -> dict:
        """
        Extract key components from the spec.

        Returns:
            dict: Dictionary with version, info, paths, schemas, security.
        """
        if not self.spec:
            raise ValueError("Spec not loaded. Call load_spec() first.")

        return {
            "version": self.spec.get("openapi"),
            "info": self.spec.get("info", {}),
            "paths": self.spec.get("paths", {}),
            "schemas": self.spec.get("components", {}).get("schemas", {}),
            "security": self.spec.get("security", []),
        }

    def summary(self) -> str:
        """
        Generate a human-readable summary of the spec.

        Returns:
            str: Summary string with key details.
        """
        if not self.spec:
            raise ValueError("Spec not loaded. Call load_spec() first.")

        info = self.spec.get("info", {})
        title = info.get("title", "Unknown API")
        version = info.get("version", "Unknown")
        num_paths = len(self.spec.get("paths", {}))
        num_schemas = len(self.spec.get("components", {}).get("schemas", {}))

        return (
            f"OpenAPI Spec Summary:\n"
            f"  Title: {title}\n"
            f"  Version: {version}\n"
            f"  OpenAPI Version: {self.spec.get('openapi')}\n"
            f"  Paths: {num_paths}\n"
            f"  Schemas: {num_schemas}\n"
        )

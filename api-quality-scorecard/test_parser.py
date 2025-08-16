#!/usr/bin/env python3
"""
Test script for the OpenAPI parser component.
This helps verify that your parser can load and understand OpenAPI specifications.
"""

import os
import sys
from pathlib import Path
from parser import OpenAPIParser


def test_parser_implementation():
    """Test that the parser can be imported and basic functionality works."""
    print("🔍 Testing OpenAPI Parser Implementation...")
    try:
        parser = OpenAPIParser("examples/simple-api.yaml")
        print("✅ Parser import & initialization successful")
        return True
    except ImportError as e:
        print(f"❌ Parser import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Parser initialization failed: {e}")
        return False


def test_example_specs():
    """Test parsing of example specifications."""
    print("\n📖 Testing Example Specifications...")

    example_files = [
        "examples/simple-api.yaml",
    ]

    results = []

    for spec_file in example_files:
        if not os.path.exists(spec_file):
            print(f"⚠️ Example file not found: {spec_file}")
            continue

        print(f"Testing: {spec_file}")
        try:
            parser = OpenAPIParser(spec_file)
            parser.load_spec()
            assert parser.validate()
            components = parser.extract_components()
            print(f"  ✅ {spec_file} parsed successfully")
            print(f"     Components: {list(components.keys())}")
            results.append(True)
        except Exception as e:
            print(f"  ❌ {spec_file} failed: {e}")
            results.append(False)

    return all(results)


def test_spec_validation():
    """Test OpenAPI specification validation."""
    print("\n🔬 Testing Specification Validation...")

    test_cases = [
        {
            "name": "Valid minimal spec",
            "spec": {
                "openapi": "3.0.0",
                "info": {"title": "Test API", "version": "1.0.0"},
                "paths": {},
            },
            "should_pass": True,
        },
        {
            "name": "Missing required fields",
            "spec": {
                "openapi": "3.0.0",
                "info": {"title": "Test API"},  # Missing version
            },
            "should_pass": False,
        },
        {
            "name": "Invalid OpenAPI version",
            "spec": {
                "openapi": "2.0",
                "info": {"title": "Test API", "version": "1.0.0"},
                "paths": {},
            },
            "should_pass": False,
        },
    ]

    parser = OpenAPIParser("examples/simple-api.yaml")  # dummy init

    for case in test_cases:
        print(f"Testing: {case['name']}")
        parser.spec = case["spec"]  # inject spec directly
        try:
            result = parser.validate()
            if result == case["should_pass"]:
                print("  ✅ Validation result as expected")
            else:
                print("  ❌ Unexpected validation result")
                return False
        except Exception:
            if case["should_pass"] is False:
                print("  ✅ Error raised as expected")
            else:
                print("  ❌ Unexpected error")
                return False

    return True


def test_error_handling():
    """Test parser error handling with problematic inputs."""
    print("\n🚨 Testing Error Handling...")

    # Non-existent file
    try:
        parser = OpenAPIParser("non-existent-file.yaml")
        parser.load_spec()
        print("  ❌ Expected FileNotFoundError")
        return False
    except FileNotFoundError:
        print("  ✅ FileNotFoundError caught as expected")

    # Invalid YAML
    bad_yaml = "invalid: [unclosed"
    try:
        tmpfile = Path("tmp.yaml")
        tmpfile.write_text(bad_yaml)
        parser = OpenAPIParser(str(tmpfile))
        parser.load_spec()
        print("  ❌ Expected YAML parsing error")
        return False
    except Exception:
        print("  ✅ Invalid YAML error caught as expected")
    finally:
        if Path("tmp.yaml").exists():
            Path("tmp.yaml").unlink()

    return True


def main():
    """Run all parser tests."""
    print("🧪 OpenAPI Parser Test Suite")
    print("=" * 50)

    tests = [
        test_parser_implementation,
        test_example_specs,
        test_spec_validation,
        test_error_handling,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed with error: {e}")
            results.append(False)

    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 All tests passed! ({passed}/{total})")
        print("\n✅ Parser implementation is ready for development")
        return 0
    else:
        print(f"❌ Some tests failed ({passed}/{total})")
        return 1


if __name__ == "__main__":
    sys.exit(main())

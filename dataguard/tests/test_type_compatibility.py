"""
Unit tests for DataGuard Type Compatibility Engine.
Verifies type normalization, safe widening, narrowing prevention, and cross-domain compatibility.
"""

import pytest
from dataguard.schema.type_compatibility import TypeCompatibilityEngine, DiffSeverity

def test_identical_types_are_safe():
    is_compat, sev, _ = TypeCompatibilityEngine.check_type_compatibility("string", "string")
    assert is_compat is True
    assert sev == DiffSeverity.SAFE

def test_type_normalization_sql_types():
    assert TypeCompatibilityEngine.normalize_type("VARCHAR(255)") == "string"
    assert TypeCompatibilityEngine.normalize_type("NUMERIC(10, 2)") == "numeric"
    assert TypeCompatibilityEngine.normalize_type("INT4") == "integer"
    assert TypeCompatibilityEngine.normalize_type("INT8") == "bigint"
    assert TypeCompatibilityEngine.normalize_type("TIMESTAMPTZ") == "timestamp"

def test_safe_widening_integer_to_bigint():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("integer", "bigint")
    assert is_compat is True
    assert sev == DiffSeverity.SAFE
    assert "widening" in explanation.lower()

def test_safe_widening_integer_to_numeric():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("integer", "numeric")
    assert is_compat is True
    assert sev == DiffSeverity.SAFE

def test_safe_widening_float_to_numeric():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("float", "numeric")
    assert is_compat is True
    assert sev == DiffSeverity.SAFE

def test_narrowing_float_to_integer_is_breaking():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("float", "integer")
    assert is_compat is False
    assert sev == DiffSeverity.BREAKING
    assert "narrowing" in explanation.lower()

def test_narrowing_bigint_to_integer_is_breaking():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("bigint", "integer")
    assert is_compat is False
    assert sev == DiffSeverity.BREAKING
    assert "overflow" in explanation.lower()

def test_cross_domain_integer_to_string_is_breaking():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("integer", "string")
    assert is_compat is False
    assert sev == DiffSeverity.BREAKING

def test_cross_domain_string_to_integer_is_breaking():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("string", "integer")
    assert is_compat is False
    assert sev == DiffSeverity.BREAKING

def test_boolean_to_string_is_breaking():
    is_compat, sev, explanation = TypeCompatibilityEngine.check_type_compatibility("boolean", "string")
    assert is_compat is False
    assert sev == DiffSeverity.BREAKING

"""
DataGuard Type Compatibility Engine
Defines explicit type normalization, compatibility rules, widening/narrowing semantics,
and severity classification for data contract schema changes.
"""

from enum import Enum
from typing import Tuple, Dict, Any, Optional

class DiffSeverity(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    BREAKING = "BREAKING"

class TypeCompatibilityEngine:
    """
    Evaluates type transitions between contract versions.
    Enforces deterministic compatibility policy:
    - Identical types: SAFE (no issue)
    - Widening (e.g. integer -> bigint, integer -> numeric): SAFE
    - Narrowing (e.g. float -> integer, bigint -> integer): BREAKING
    - Incompatible domains (e.g. string <-> integer, boolean <-> string): BREAKING
    """

    # Mapping of common SQL and programming types to normalized standard contract types
    TYPE_NORMALIZATION: Dict[str, str] = {
        "int": "integer",
        "int4": "integer",
        "integer": "integer",
        "int8": "bigint",
        "bigint": "bigint",
        "smallint": "integer",
        "tinyint": "integer",
        "float": "float",
        "float4": "float",
        "float8": "float",
        "double": "float",
        "double precision": "float",
        "real": "float",
        "numeric": "numeric",
        "decimal": "numeric",
        "str": "string",
        "string": "string",
        "text": "string",
        "varchar": "string",
        "char": "string",
        "bool": "boolean",
        "boolean": "boolean",
        "date": "timestamp",
        "datetime": "timestamp",
        "time": "timestamp",
        "timestamp": "timestamp",
        "timestamptz": "timestamp",
    }

    # Explicit widening graph: from_type -> set of allowed wider to_types (SAFE)
    SAFE_WIDENING: Dict[str, set] = {
        "integer": {"bigint", "numeric", "float"},
        "bigint": {"numeric"},
        "float": {"numeric"},
    }

    @classmethod
    def normalize_type(cls, raw_type: Optional[str]) -> str:
        """
        Normalizes a type string into a canonical DataGuard contract type.
        Strips precision/length parameters (e.g. 'VARCHAR(255)' -> 'varchar' -> 'string').
        """
        if not raw_type:
            return "string"

        cleaned = str(raw_type).strip().lower()
        # Remove parenthesized length/precision specifiers like varchar(255) or numeric(10,2)
        if "(" in cleaned:
            base_type = cleaned.split("(", 1)[0].strip()
        else:
            base_type = cleaned

        return cls.TYPE_NORMALIZATION.get(base_type, base_type)

    @classmethod
    def check_type_compatibility(
        cls, 
        old_type_str: str, 
        new_type_str: str
    ) -> Tuple[bool, DiffSeverity, str]:
        """
        Determines if transitioning from old_type to new_type is compatible.
        Returns:
            (is_compatible: bool, severity: DiffSeverity, explanation: str)
        """
        old_norm = cls.normalize_type(old_type_str)
        new_norm = cls.normalize_type(new_type_str)

        if old_norm == new_norm:
            return True, DiffSeverity.SAFE, f"Types are identical ('{old_norm}')."

        # Check safe widening
        if old_norm in cls.SAFE_WIDENING and new_norm in cls.SAFE_WIDENING[old_norm]:
            return True, DiffSeverity.SAFE, (
                f"Safe type widening: '{old_norm}' -> '{new_norm}'. "
                f"Existing '{old_norm}' values fit without precision or range loss."
            )

        # Narrowing conversions
        if old_norm in {"float", "numeric"} and new_norm == "integer":
            return False, DiffSeverity.BREAKING, (
                f"Narrowing type conversion: '{old_norm}' -> '{new_norm}'. "
                f"Fractional precision will be truncated."
            )

        if old_norm == "bigint" and new_norm == "integer":
            return False, DiffSeverity.BREAKING, (
                f"Narrowing type conversion: 'bigint' -> 'integer'. "
                f"Large integers may cause overflow."
            )

        # Cross-domain incompatible transitions
        return False, DiffSeverity.BREAKING, (
            f"Incompatible cross-domain type change: '{old_norm}' -> '{new_norm}'. "
            f"Downstream consumers and producers will experience type mismatch errors."
        )

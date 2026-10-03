"""
DataGuard Contract Validator Module
Validates YAML data contract structure, mandatory fields, types, and constraints.
"""

from typing import Dict, Any, List, Tuple

REQUIRED_ROOT_KEYS = ["dataset", "version", "owner", "description", "freshness_sla_minutes", "columns", "constraints"]
MANDATORY_COLUMN_KEYS = ["name", "type", "nullable", "unique", "description"]
VALID_COLUMN_TYPES = ["string", "numeric", "integer", "timestamp", "float"]
VALID_STATUSES = ["ACTIVE", "DEPRECATED", "DRAFT"]

class ContractValidationError(Exception):
    """Raised when a data contract violates schema specification rules."""
    pass

class ContractValidator:
    @staticmethod
    def validate_contract(contract: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates contract dictionary against specification rules.
        Returns (is_valid, list_of_errors).
        """
        errors: List[str] = []

        if not isinstance(contract, dict):
            return False, ["Contract payload must be a dictionary object."]

        # 1. Root keys validation
        for key in REQUIRED_ROOT_KEYS:
            if key not in contract:
                errors.append(f"Missing mandatory root field '{key}'.")

        dataset_name = contract.get("dataset")
        if not dataset_name or not isinstance(dataset_name, str):
            errors.append("Root field 'dataset' must be a non-empty string.")

        version = contract.get("version")
        if not version or not isinstance(version, str):
            errors.append("Root field 'version' must be a non-empty string (e.g. 'v1.0.0').")

        status = contract.get("status", "ACTIVE")
        if status not in VALID_STATUSES:
            errors.append(f"Invalid status '{status}'. Must be one of {VALID_STATUSES}.")

        sla = contract.get("freshness_sla_minutes")
        if sla is not None and (not isinstance(sla, int) or sla <= 0):
            errors.append("Field 'freshness_sla_minutes' must be a positive integer.")

        # 2. Columns validation
        columns = contract.get("columns")
        if not isinstance(columns, list) or len(columns) == 0:
            errors.append("Root field 'columns' must be a non-empty list of column definitions.")
        else:
            col_names = set()
            for idx, col in enumerate(columns):
                if not isinstance(col, dict):
                    errors.append(f"Column item at index {idx} is not a dictionary object.")
                    continue

                col_name = col.get("name")
                if not col_name:
                    errors.append(f"Column index {idx} missing 'name'.")
                elif col_name in col_names:
                    errors.append(f"Duplicate column name '{col_name}' detected.")
                else:
                    col_names.add(col_name)

                for key in MANDATORY_COLUMN_KEYS:
                    if key not in col:
                        errors.append(f"Column '{col_name or idx}' missing mandatory field '{key}'.")

                col_type = col.get("type")
                if col_type and col_type not in VALID_COLUMN_TYPES:
                    errors.append(f"Column '{col_name}' has invalid type '{col_type}'. Must be one of {VALID_COLUMN_TYPES}.")

                # Enum validation
                if "allowed_values" in col:
                    enums = col["allowed_values"]
                    if not isinstance(enums, list) or len(enums) == 0:
                        errors.append(f"Column '{col_name}' 'allowed_values' must be a non-empty list.")

                # Numeric min/max validation
                if "min" in col and "max" in col:
                    if col["min"] > col["max"]:
                        errors.append(f"Column '{col_name}' min ({col['min']}) > max ({col['max']}).")

        is_valid = len(errors) == 0
        return is_valid, errors

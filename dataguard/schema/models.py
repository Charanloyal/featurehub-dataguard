"""
DataGuard Schema Diff Pydantic Data Models
Defines typed models for schema changes, classifications, results, and API payloads.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DiffSeverity(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    BREAKING = "BREAKING"

class FlexibleChangeType(str):
    """String wrapper that allows aliases for backward and specification compatibility."""
    def __eq__(self, other: Any) -> bool:
        if super().__eq__(other):
            return True
        aliases = {
            "ENUM_VALUES_ADDED": {"ENUM_VALUE_ADDED", "ENUM_VALUES_ADDED"},
            "ENUM_VALUE_ADDED": {"ENUM_VALUE_ADDED", "ENUM_VALUES_ADDED"},
            "ENUM_VALUES_REMOVED": {"ENUM_VALUE_REMOVED", "ENUM_VALUES_REMOVED"},
            "ENUM_VALUE_REMOVED": {"ENUM_VALUE_REMOVED", "ENUM_VALUES_REMOVED"},
            "CONSTRAINT_TIGHTENED": {"CONSTRAINT_TIGHTENED", "RANGE_TIGHTENED"},
            "RANGE_TIGHTENED": {"CONSTRAINT_TIGHTENED", "RANGE_TIGHTENED"},
            "CONSTRAINT_RELAXED": {"CONSTRAINT_RELAXED", "RANGE_EXPANDED"},
            "RANGE_EXPANDED": {"CONSTRAINT_RELAXED", "RANGE_EXPANDED"},
        }
        if self in aliases and str(other) in aliases[self]:
            return True
        return False

    def __hash__(self) -> int:
        return super().__hash__()

class ChangeType(str, Enum):
    COLUMN_ADDED = "COLUMN_ADDED"
    COLUMN_REMOVED = "COLUMN_REMOVED"
    COLUMN_RENAMED = "COLUMN_RENAMED"
    TYPE_CHANGED = "TYPE_CHANGED"
    NULLABILITY_CHANGED = "NULLABILITY_CHANGED"
    UNIQUE_CHANGED = "UNIQUE_CHANGED"
    ENUM_VALUE_ADDED = "ENUM_VALUE_ADDED"
    ENUM_VALUES_ADDED = "ENUM_VALUES_ADDED"
    ENUM_VALUE_REMOVED = "ENUM_VALUE_REMOVED"
    ENUM_VALUES_REMOVED = "ENUM_VALUES_REMOVED"
    RANGE_EXPANDED = "RANGE_EXPANDED"
    RANGE_TIGHTENED = "RANGE_TIGHTENED"
    CONSTRAINT_RELAXED = "CONSTRAINT_RELAXED"
    CONSTRAINT_TIGHTENED = "CONSTRAINT_TIGHTENED"
    CONSTRAINT_ADDED = "CONSTRAINT_ADDED"
    CONSTRAINT_REMOVED = "CONSTRAINT_REMOVED"
    SLA_CHANGED = "SLA_CHANGED"
    DESCRIPTION_CHANGED = "DESCRIPTION_CHANGED"
    METADATA_CHANGED = "METADATA_CHANGED"

class SchemaChange(BaseModel):
    column: Optional[str] = Field(None, description="Affected column name, if applicable")
    change_type: ChangeType = Field(..., description="Category of detected modification")
    old_value: Optional[Any] = Field(None, description="Previous value or configuration")
    new_value: Optional[Any] = Field(None, description="New value or configuration")
    severity: DiffSeverity = Field(..., description="Compatibility severity classification")
    description: str = Field(..., description="Human-readable explanation of the change and its impact")

    def __getitem__(self, item: str) -> Any:
        if item == "column_name":
            return self.column
        if item == "change_type":
            val = self.change_type.value if hasattr(self.change_type, "value") else str(self.change_type)
            return FlexibleChangeType(val)
        if hasattr(self, item):
            val = getattr(self, item)
            if hasattr(val, "value"):
                return val.value
            return val
        d = self.to_dict()
        if item in d:
            return d[item]
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return item in {"column", "column_name", "change_type", "old_value", "new_value", "severity", "description"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "column_name": self.column,  # Backwards compatibility
            "change_type": self.change_type.value if hasattr(self.change_type, "value") else str(self.change_type),
            "old_value": self.old_value,
            "new_value": self.new_value,
            "severity": self.severity.value if hasattr(self.severity, "value") else str(self.severity),
            "description": self.description,
        }

class SchemaDiffResult(BaseModel):
    dataset: Optional[str] = Field(None, description="Name of the evaluated dataset")
    from_version: Optional[str] = Field(None, description="Baseline contract version")
    to_version: Optional[str] = Field(None, description="Target contract version")
    classification: DiffSeverity = Field(..., description="Overall compatibility rating (SAFE, WARNING, BREAKING)")
    is_breaking: bool = Field(..., description="True if any changes are classified as BREAKING")
    total_changes: int = Field(0, description="Total count of detected modifications")
    changes: List[SchemaChange] = Field(default_factory=list, description="Detailed list of detected changes")
    summary: Optional[str] = Field(None, description="High-level human-readable summary")
    recommendation: Optional[str] = Field(None, description="CI recommendation: BLOCK MERGE, APPROVE WITH WARNING, or APPROVE")

    def __getitem__(self, item: str) -> Any:
        if item == "baseline_version":
            return self.from_version
        if item == "target_version":
            return self.to_version
        if hasattr(self, item):
            val = getattr(self, item)
            if hasattr(val, "value"):
                return val.value
            return val
        d = self.to_dict()
        if item in d:
            return d[item]
        raise KeyError(item)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "from_version": self.from_version,
            "baseline_version": self.from_version,  # Backwards compatibility
            "to_version": self.to_version,
            "target_version": self.to_version,      # Backwards compatibility
            "classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "is_breaking": self.is_breaking,
            "total_changes": self.total_changes,
            "changes": [c.to_dict() for c in self.changes],
            "summary": self.summary,
            "recommendation": self.recommendation,
        }

class SchemaDiffRequest(BaseModel):
    dataset: Optional[str] = Field(None, description="Dataset name registered in PostgreSQL")
    from_version: Optional[str] = Field(None, description="Baseline version tag (e.g. 'v1.0.0')")
    to_version: Optional[str] = Field(None, description="Target version tag (e.g. 'v1.1.0')")
    baseline_contract: Optional[Dict[str, Any]] = Field(None, description="Direct baseline contract dictionary (for ad-hoc checks)")
    target_contract: Optional[Dict[str, Any]] = Field(None, description="Direct target contract dictionary (for ad-hoc checks)")

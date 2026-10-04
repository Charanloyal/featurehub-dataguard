"""
DataGuard CI/CD Gating Models (Phase H).
Defines schemas for automated PR schema compatibility checks,
contract validation gates, quality regression results, and merge decisions.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GatingVerdict(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    BREAKING = "BREAKING"


class GatingChange(BaseModel):
    column: Optional[str] = None
    change_type: str
    severity: str
    description: str
    remediation: Optional[str] = None


class ContractGatingResult(BaseModel):
    dataset_name: str
    file_path: Optional[str] = None
    contract_valid: bool = True
    contract_errors: List[str] = Field(default_factory=list)
    verdict: GatingVerdict = GatingVerdict.SAFE
    can_merge: bool = True
    is_breaking: bool = False
    changes: List[GatingChange] = Field(default_factory=list)
    breaking_count: int = 0
    warning_count: int = 0
    safe_count: int = 0
    quality_regression_passed: bool = True
    quality_score: Optional[float] = None
    quality_errors: List[str] = Field(default_factory=list)


class PRGatingSummary(BaseModel):
    verdict: GatingVerdict
    can_merge: bool
    total_contracts_analyzed: int
    contracts_with_breaking: int
    contracts_with_warnings: int
    contracts_safe: int
    total_breaking_changes: int
    total_warning_changes: int
    total_safe_changes: int
    results: List[ContractGatingResult] = Field(default_factory=list)
    markdown_report: str = ""
    exit_code: int = 0

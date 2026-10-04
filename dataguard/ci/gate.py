"""
DataGuard CI/CD Compatibility & Quality Gating Engine (Phase H).
Orchestrates automated pre-merge gating for Pull Requests:
Contract Validation -> Schema Diff Engine -> Data Quality Regression -> Merge Verdict.
"""

import os
import sys
import yaml
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from dataguard.ci.models import (
    GatingVerdict,
    GatingChange,
    ContractGatingResult,
    PRGatingSummary
)
from dataguard.contracts.validator import ContractValidator
from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.models import DiffSeverity, SchemaChange
from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.datasets import DatasetCatalog

logger = logging.getLogger("dataguard.ci.gate")


class CICDContractGatingEngine:
    """
    Automated CI/CD Gating Engine evaluating contract modifications on PRs.
    Enforces non-breaking contract evolution policies and blocks breaking modifications.
    """

    @classmethod
    def evaluate_contract_change(
        cls,
        baseline_contract: Optional[Dict[str, Any]],
        target_contract: Dict[str, Any],
        dataset_name: Optional[str] = None,
        file_path: Optional[str] = None,
        validate_quality: bool = True
    ) -> ContractGatingResult:
        """
        Executes the three-phase CI verification:
        1. Contract Structural Validation
        2. Schema Diff Compatibility Analysis
        3. Data Quality Regression Testing
        """
        ds_name = dataset_name or target_contract.get("dataset") or (
            baseline_contract.get("dataset") if baseline_contract else "unknown_dataset"
        )
        result = ContractGatingResult(dataset_name=ds_name, file_path=file_path)

        # ----------------------------------------------------------------------
        # Stage 1: Contract Structural Validation
        # ----------------------------------------------------------------------
        is_valid, val_errors = ContractValidator.validate_contract(target_contract)
        if not is_valid or val_errors:
            result.contract_valid = False
            result.contract_errors = val_errors
            result.verdict = GatingVerdict.BREAKING
            result.can_merge = False
            result.is_breaking = True
            result.breaking_count += len(val_errors)
            for err in val_errors:
                result.changes.append(GatingChange(
                    column=None,
                    change_type="INVALID_CONTRACT_STRUCTURE",
                    severity="BREAKING",
                    description=f"Structural syntax violation: {err}",
                    remediation="Correct YAML structure according to DataGuard contract specification."
                ))
            return result

        # ----------------------------------------------------------------------
        # Stage 2: Schema Diff Compatibility Analysis
        # ----------------------------------------------------------------------
        if baseline_contract is not None:
            diff_res = SchemaDiffEngine.compare_contracts(
                baseline_contract=baseline_contract,
                target_contract=target_contract
            )

            for ch in diff_res.changes:
                sev_str = ch.severity.value if hasattr(ch.severity, "value") else str(ch.severity)
                remediation = cls._generate_remediation(ch)

                g_change = GatingChange(
                    column=ch.column,
                    change_type=ch.change_type.value if hasattr(ch.change_type, "value") else str(ch.change_type),
                    severity=sev_str,
                    description=ch.description,
                    remediation=remediation
                )
                result.changes.append(g_change)

                if ch.severity == DiffSeverity.BREAKING:
                    result.breaking_count += 1
                elif ch.severity == DiffSeverity.WARNING:
                    result.warning_count += 1
                else:
                    result.safe_count += 1

            result.is_breaking = (result.breaking_count > 0)
        else:
            # Brand new contract addition is SAFE
            result.safe_count += 1
            result.changes.append(GatingChange(
                column=None,
                change_type="NEW_CONTRACT_ADDED",
                severity="SAFE",
                description=f"New data contract registered for dataset '{ds_name}'.",
                remediation="None required."
            ))

        # ----------------------------------------------------------------------
        # Stage 3: Data Quality Regression Testing
        # ----------------------------------------------------------------------
        if validate_quality and not result.is_breaking:
            try:
                sample_df = DatasetCatalog.load_dataset(ds_name)
                if sample_df is not None and not sample_df.empty:
                    runner = DataQualityRunner()
                    q_res = runner.run_validation(
                        dataset_name=ds_name,
                        df=sample_df,
                        contract=target_contract,
                        validate_referential=False,
                        validate_freshness=False
                    )
                    result.quality_score = q_res.quality_score
                    if q_res.quality_score < 70.0:
                        result.quality_regression_passed = False
                        result.quality_errors.append(
                            f"Quality score regressed to {q_res.quality_score:.1f}% on sample dataset."
                        )
            except Exception as e:
                logger.warning("Quality regression check skipped for %s: %s", ds_name, e)

        # ----------------------------------------------------------------------
        # Stage 4: Formulate Verdict
        # ----------------------------------------------------------------------
        if result.is_breaking or not result.contract_valid or not result.quality_regression_passed:
            result.verdict = GatingVerdict.BREAKING
            result.can_merge = False
        elif result.warning_count > 0:
            result.verdict = GatingVerdict.WARNING
            result.can_merge = True
        else:
            result.verdict = GatingVerdict.SAFE
            result.can_merge = True

        return result

    @classmethod
    def _generate_remediation(cls, change: SchemaChange) -> str:
        """Provides actionable migration and remediation advice for detected changes."""
        ch_type = change.change_type.value if hasattr(change.change_type, "value") else str(change.change_type)
        col = change.column or "column"

        if "REMOVED" in ch_type and "COLUMN" in ch_type:
            return (
                f"Column removal is BREAKING for downstream consumers. Instead of dropping '{col}', "
                f"deprecate it first, maintain nullability, or publish a major version (v2.0.0)."
            )
        elif "TYPE_CHANGED" in ch_type:
            return (
                f"Incompatible type shift on '{col}'. Ensure consumer ETL pipelines and schema registries "
                f"support the new physical type, or use a non-breaking widening type."
            )
        elif "NULLAB" in ch_type.upper():
            return (
                f"Tightening nullability on '{col}' will reject records containing NULLs. "
                f"Backfill missing values before enforcing 'nullable: false'."
            )
        elif "ENUM" in ch_type and "REMOVED" in ch_type:
            return (
                f"Removing allowed enum values will cause validation failures for existing events. "
                f"Deprecate values without removing them immediately."
            )
        elif "CONSTRAINT" in ch_type or "RANGE" in ch_type:
            return "Tightened bounds may reject edge-case values. Verify historical distribution bounds."
        elif "ADDED" in ch_type and "NON_NULLABLE" in ch_type:
            return f"Adding non-nullable column '{col}' requires a default value for historical backfills."

        return "Safe evolutionary change. No migration steps required."

    @classmethod
    def evaluate_pr(
        cls,
        contracts_to_evaluate: List[Tuple[Optional[Dict[str, Any]], Dict[str, Any], str]],
        allow_breaking: bool = False,
        validate_quality: bool = True
    ) -> PRGatingSummary:
        """
        Evaluates a batch of modified contracts (e.g. from git diff).
        contracts_to_evaluate: list of (baseline_dict, target_dict, file_path)
        """
        results: List[ContractGatingResult] = []
        breaking_count = 0
        warning_count = 0
        safe_count = 0
        contracts_breaking = 0
        contracts_warning = 0
        contracts_safe = 0

        for baseline, target, path in contracts_to_evaluate:
            res = cls.evaluate_contract_change(
                baseline_contract=baseline,
                target_contract=target,
                file_path=path,
                validate_quality=validate_quality
            )
            results.append(res)

            breaking_count += res.breaking_count
            warning_count += res.warning_count
            safe_count += res.safe_count

            if res.verdict == GatingVerdict.BREAKING:
                contracts_breaking += 1
            elif res.verdict == GatingVerdict.WARNING:
                contracts_warning += 1
            else:
                contracts_safe += 1

        # Formulate Overall PR Decision
        if contracts_breaking > 0 and not allow_breaking:
            overall_verdict = GatingVerdict.BREAKING
            can_merge = False
            exit_code = 1
        elif contracts_warning > 0:
            overall_verdict = GatingVerdict.WARNING
            can_merge = True
            exit_code = 0
        else:
            overall_verdict = GatingVerdict.SAFE
            can_merge = True
            exit_code = 0

        summary = PRGatingSummary(
            verdict=overall_verdict,
            can_merge=can_merge,
            total_contracts_analyzed=len(contracts_to_evaluate),
            contracts_with_breaking=contracts_breaking,
            contracts_with_warnings=contracts_warning,
            contracts_safe=contracts_safe,
            total_breaking_changes=breaking_count,
            total_warning_changes=warning_count,
            total_safe_changes=safe_count,
            results=results,
            exit_code=exit_code
        )

        summary.markdown_report = cls.generate_markdown_report(summary)
        return summary

    @classmethod
    def generate_markdown_report(cls, summary: PRGatingSummary) -> str:
        """
        Generates clean, GitHub-flavored Markdown PR summary table.
        """
        if summary.verdict == GatingVerdict.SAFE:
            header_badge = "## ✅ DataGuard CI Gate: MERGE APPROVED (SAFE)"
            callout = "> **All contract changes are backward-compatible.** No breaking modifications or quality regressions detected."
        elif summary.verdict == GatingVerdict.WARNING:
            header_badge = "## ⚠️ DataGuard CI Gate: REVIEW REQUIRED (WARNING)"
            callout = "> **Contract changes contain potentially sensitive modifications.** Review column constraints and SLA changes before merging."
        else:
            header_badge = "## ❌ DataGuard CI Gate: MERGE BLOCKED (BREAKING CHANGES)"
            callout = "> **PR contains breaking contract changes.** Merging is blocked to prevent downstream pipeline failures and schema mismatch errors."

        lines = [
            header_badge,
            "",
            callout,
            "",
            "### Summary Overview",
            f"- **Overall Verdict**: `{summary.verdict.value}`",
            f"- **Merge Status**: `{'ALLOWED' if summary.can_merge else 'BLOCKED'}`",
            f"- **Contracts Evaluated**: `{summary.total_contracts_analyzed}`",
            f"- **Breaking Changes**: `{summary.total_breaking_changes}`",
            f"- **Warning Changes**: `{summary.total_warning_changes}`",
            f"- **Safe Changes**: `{summary.total_safe_changes}`",
            "",
            "### Contract Evaluation Breakdown",
            "",
            "| Dataset | File | Verdict | Breaking | Warnings | Safe | Quality Status |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |"
        ]

        for r in summary.results:
            verdict_icon = "❌ BREAKING" if r.verdict == GatingVerdict.BREAKING else (
                "⚠️ WARNING" if r.verdict == GatingVerdict.WARNING else "✅ SAFE"
            )
            q_status = f"{r.quality_score:.1f}%" if r.quality_score is not None else "N/A"
            if not r.quality_regression_passed:
                q_status = "❌ REGRESSED"

            lines.append(
                f"| `{r.dataset_name}` | `{r.file_path or 'inline'}` | {verdict_icon} | {r.breaking_count} | {r.warning_count} | {r.safe_count} | {q_status} |"
            )

        # Detailed Changes Table if any changes exist
        all_changes: List[Tuple[str, GatingChange]] = []
        for r in summary.results:
            for ch in r.changes:
                all_changes.append((r.dataset_name, ch))

        if all_changes:
            lines.extend([
                "",
                "### Detailed Schema Modifications & Remediation",
                "",
                "| Dataset | Column | Severity | Change Type | Description | Recommended Action |",
                "| :--- | :--- | :---: | :--- | :--- | :--- |"
            ])
            for ds, ch in all_changes:
                sev_icon = "🔴 BREAKING" if ch.severity == "BREAKING" else (
                    "🟡 WARNING" if ch.severity == "WARNING" else "🟢 SAFE"
                )
                col_str = f"`{ch.column}`" if ch.column else "*(contract)*"
                lines.append(
                    f"| `{ds}` | {col_str} | {sev_icon} | `{ch.change_type}` | {ch.description} | {ch.remediation} |"
                )

        lines.extend([
            "",
            "---",
            "*Automated check powered by [DataGuard](https://github.com/Charanloyal/dataguard) CI/CD Gating Engine.*"
        ])

        return "\n".join(lines)

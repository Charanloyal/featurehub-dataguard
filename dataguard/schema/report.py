"""
DataGuard Human-Readable Schema Diff Report Generator
Generates clean, objective, structured text and markdown reports suitable for
developers, PR reviewers, and CI/CD pipeline blocking logs.
"""

from typing import Union, Dict, Any
from dataguard.schema.models import SchemaDiffResult, DiffSeverity

def generate_human_report(diff_result: Union[SchemaDiffResult, Dict[str, Any]]) -> str:
    """
    Renders a clear, objective human-readable report from a SchemaDiffResult.
    Follows strict compatibility policy recommendations:
    - BREAKING -> BLOCK MERGE
    - WARNING  -> APPROVE WITH WARNING (Review Required)
    - SAFE     -> APPROVE (Safe to Merge)
    """
    if isinstance(diff_result, dict):
        dataset = diff_result.get("dataset", "unknown_dataset")
        from_v = diff_result.get("from_version") or diff_result.get("baseline_version") or "unknown"
        to_v = diff_result.get("to_version") or diff_result.get("target_version") or "unknown"
        classification = diff_result.get("classification", "SAFE")
        changes = diff_result.get("changes", [])
    else:
        dataset = diff_result.dataset or "unknown_dataset"
        from_v = diff_result.from_version or "unknown"
        to_v = diff_result.to_version or "unknown"
        classification = diff_result.classification.value if hasattr(diff_result.classification, "value") else str(diff_result.classification)
        changes = [c.to_dict() if hasattr(c, "to_dict") else c for c in diff_result.changes]

    # Header badge
    if classification == "BREAKING":
        header = "============================================================\n" \
                 "             *** BREAKING CHANGE DETECTED ***               \n" \
                 "============================================================"
        recommendation = "BLOCK MERGE\n(Breaking schema changes will break downstream consumers or producers)"
    elif classification == "WARNING":
        header = "============================================================\n" \
                 "             [!] WARNING: COMPATIBILITY ALERT [!]           \n" \
                 "============================================================"
        recommendation = "APPROVE WITH WARNING\n(Producer updates or pipeline migration required)"
    else:
        header = "============================================================\n" \
                 "             [+] SAFE: BACKWARD COMPATIBLE [+]              \n" \
                 "============================================================"
        recommendation = "APPROVE\n(Schema modifications are 100% backward-compatible)"

    lines = [
        header,
        f"\nDataset:\n  {dataset}\n",
        f"Version Transition:\n  {from_v} -> {to_v}\n",
        f"Overall Classification:\n  {classification}\n",
        f"Total Modifications Detected:\n  {len(changes)}\n",
        "------------------------------------------------------------",
        "Detailed Changes:",
        "------------------------------------------------------------"
    ]

    if not changes:
        lines.append("  (No schema changes detected; contracts are 100% identical)")
    else:
        for idx, chg in enumerate(changes, start=1):
            col = chg.get("column") or chg.get("column_name") or "(root)"
            ctype = chg.get("change_type", "MODIFIED")
            sev = chg.get("severity", "SAFE")
            old_val = chg.get("old_value")
            new_val = chg.get("new_value")
            desc = chg.get("description", "")

            change_block = [
                f"\n{idx}. [{sev}] Column/Entity: '{col}'",
                f"   Change Type: {ctype}"
            ]
            if old_val is not None or new_val is not None:
                change_block.append(f"   Transition : {old_val} -> {new_val}")
            if desc:
                change_block.append(f"   Impact     : {desc}")

            lines.append("\n".join(change_block))

    lines.append("\n------------------------------------------------------------")
    lines.append(f"Recommendation:\n  {recommendation}")
    lines.append("============================================================\n")

    return "\n".join(lines)

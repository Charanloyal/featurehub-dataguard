#!/usr/bin/env python3
"""
DataGuard Schema Diff CLI Tool
Compares two versions of a data contract (from PostgreSQL registry or YAML files)
and outputs machine-readable and human-readable compatibility analysis.
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dataguard.contracts.registry import ContractRegistryService, ContractNotFoundError
from dataguard.schema.diff import SchemaDiffEngine
from dataguard.schema.report import generate_human_report
from dataguard.schema.models import DiffSeverity, ChangeType


def format_cli_output(diff_res) -> str:
    """Formats schema diff results strictly matching standard CLI output format."""
    lines = []
    dataset = diff_res.dataset or "unknown"
    from_ver = diff_res.from_version or "v1"
    to_ver = diff_res.to_version or "v2"

    lines.append(f"Dataset: {dataset}")
    lines.append(f"From: {from_ver}")
    lines.append(f"To: {to_ver}")
    lines.append("")
    lines.append("Changes:")

    if not diff_res.changes:
        lines.append("  (No schema changes detected)")
    else:
        for c in diff_res.changes:
            col = c.column or "(root)"
            c_type = str(c.change_type.value if hasattr(c.change_type, "value") else c.change_type)
            sev = str(c.severity.value if hasattr(c.severity, "value") else c.severity)

            # Determine prefix symbol
            if "ADDED" in c_type:
                sym = "+"
            elif "REMOVED" in c_type:
                sym = "-"
            else:
                sym = "~"

            # Format tag cleanly (e.g. COLUMN_ADDED -> ADDED, TYPE_CHANGED -> TYPE_CHANGED)
            display_type = c_type.replace("COLUMN_", "").replace("VALUES_", "VALUE_")
            lines.append(f"{sym} {col} [{display_type}] [{sev}] - {c.description}")

    lines.append("")
    lines.append("Overall Classification:")
    lines.append(str(diff_res.classification.value if hasattr(diff_res.classification, "value") else diff_res.classification))
    lines.append("")
    lines.append(f"Recommendation: {diff_res.recommendation or ('BLOCK MERGE' if diff_res.is_breaking else 'APPROVE')}")

    return "\n".join(lines)


def load_yaml_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Contract file not found at: {path}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"File {path} does not contain a valid dictionary contract.")
    return data


def main():
    parser = argparse.ArgumentParser(
        description="DataGuard Schema Diff & Compatibility Engine CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Mode 1: Registry-backed comparison
    parser.add_argument("--dataset", "-d", help="Name of registered dataset in PostgreSQL")
    parser.add_argument("--from-version", "-f", help="Baseline version tag (e.g. v1.0.0)")
    parser.add_argument("--to-version", "-t", help="Target version tag (e.g. v1.1.0)")

    # Mode 2: Direct file comparison
    parser.add_argument("--file1", help="Path to baseline YAML contract file")
    parser.add_argument("--file2", help="Path to target YAML contract file")

    # Options
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--report", action="store_true", help="Include full human-readable markdown report")
    parser.add_argument("--strict", action="store_true", help="Treat WARNING as failure (exit code 1)")

    args = parser.parse_args()

    # Route execution based on arguments
    if args.file1 and args.file2:
        try:
            c1 = load_yaml_file(args.file1)
            c2 = load_yaml_file(args.file2)
            diff_res = SchemaDiffEngine.compare_contracts(c1, c2)
        except Exception as e:
            print(f"Error reading YAML contracts: {e}", file=sys.stderr)
            sys.exit(2)
    elif args.dataset and args.from_version and args.to_version:
        if args.from_version == args.to_version:
            print(f"Error: --from-version and --to-version cannot be the same ('{args.from_version}').", file=sys.stderr)
            sys.exit(2)
        try:
            registry = ContractRegistryService()
            diff_res = SchemaDiffEngine.compare_versions(
                registry_service=registry,
                dataset=args.dataset,
                from_version=args.from_version,
                to_version=args.to_version
            )
        except ContractNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"Internal Error: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        parser.print_help(sys.stderr)
        print("\nError: Must provide either (--dataset, --from-version, --to-version) or (--file1, --file2).", file=sys.stderr)
        sys.exit(2)

    # Output formatting
    if args.json:
        print(json.dumps(diff_res.to_dict(), indent=2))
    elif args.report:
        print(generate_human_report(diff_res))
    else:
        print(format_cli_output(diff_res))

    # Exit code determination
    if diff_res.is_breaking:
        sys.exit(1)
    if args.strict and diff_res.classification == DiffSeverity.WARNING:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

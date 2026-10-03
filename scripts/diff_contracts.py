"""
DataGuard Schema Diff CLI Utility
Compares contracts across versions, against files, or against live PostgreSQL/SQLite database tables.
Classifies changes as SAFE, WARNING, or BREAKING.
"""

import argparse
import sys
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dataguard.schema.diff import SchemaDiffEngine, DiffSeverity
from dataguard.contracts.registry import ContractRegistryService


def format_change_line(change: dict) -> str:
    severity = change["severity"]
    col = change["column_name"]
    ctype = change["change_type"]
    desc = change["description"]
    
    if severity == "BREAKING":
        prefix = " [BREAKING]"
    elif severity == "WARNING":
        prefix = " [WARNING] "
    else:
        prefix = " [SAFE]    "
        
    return f"{prefix} [{ctype}] {col}: {desc}"

def main():
    parser = argparse.ArgumentParser(description="DataGuard Schema Diff Engine CLI")
    parser.add_argument("--dataset", help="Dataset name in registry")
    parser.add_argument("--v1", help="Baseline version (default: v1.0.0 or oldest)")
    parser.add_argument("--v2", help="Target version (default: latest)")
    parser.add_argument("--file1", help="Path to baseline YAML contract file")
    parser.add_argument("--file2", help="Path to target YAML contract file")
    parser.add_argument("--table", help="Compare dataset contract against live database table name")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if BREAKING changes detected")

    args = parser.parse_args()
    registry = ContractRegistryService()

    print("=" * 60)
    print("  DATAGUARD SCHEMA DIFF ENGINE")
    print("=" * 60)

    try:
        # Mode 1: Compare two local files
        if args.file1 and args.file2:
            p1, p2 = Path(args.file1), Path(args.file2)
            if not p1.exists() or not p2.exists():
                print(f"Error: One of the files does not exist: '{args.file1}' or '{args.file2}'")
                sys.exit(2)
            with open(p1, "r") as f:
                c1 = yaml.safe_load(f)
            with open(p2, "r") as f:
                c2 = yaml.safe_load(f)
            print(f"Comparing File: {p1.name} -> {p2.name}")
            diff_result = SchemaDiffEngine.compare_contracts(c1, c2)

        # Mode 2: Compare dataset contract against live DB table
        elif args.dataset and args.table:
            c = registry.get_contract(args.dataset, version=args.v1)
            if not c:
                print(f"Error: Contract for dataset '{args.dataset}' not found in registry.")
                sys.exit(2)
            print(f"Comparing Dataset '{args.dataset}' ({c.get('version')}) against live table '{args.table}'")
            diff_result = SchemaDiffEngine.compare_contract_to_table(c, args.table)

        # Mode 3: Compare two versions from registry
        elif args.dataset:
            v1_target = args.v1 or "v1.0.0"
            c1 = registry.get_contract(args.dataset, version=v1_target)
            if not c1:
                # Try fetching any version
                versions = registry.get_contract_versions(args.dataset)
                if not versions:
                    print(f"Error: No contract versions found for dataset '{args.dataset}'.")
                    sys.exit(2)
                v1_target = versions[0]["version"]
                c1 = registry.get_contract(args.dataset, version=v1_target)

            c2 = registry.get_contract(args.dataset, version=args.v2)
            if not c2:
                print(f"Error: Target version '{args.v2 or 'latest'}' for dataset '{args.dataset}' not found.")
                sys.exit(2)

            print(f"Comparing Dataset '{args.dataset}': {c1.get('version')} -> {c2.get('version')}")
            diff_result = SchemaDiffEngine.compare_contracts(c1, c2)

        else:
            parser.print_help()
            sys.exit(1)

        # Display Diff Results
        classification = diff_result["classification"]
        print("-" * 60)
        print(f"Overall Classification : {classification}")
        print(f"Breaking Changes       : {diff_result['is_breaking']}")
        print(f"Total Changes Detected : {diff_result['total_changes']}")
        print("-" * 60)

        if diff_result["changes"]:
            print("Changes Detail:")
            for chg in diff_result["changes"]:
                print(format_change_line(chg))
        else:
            print("No schema changes detected (schemas are identical).")

        print("=" * 60)

        if args.strict and diff_result["is_breaking"]:
            sys.exit(1)

    except Exception as e:
        print(f"Execution Error: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()

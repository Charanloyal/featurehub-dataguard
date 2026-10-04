#!/usr/bin/env python3
"""
DataGuard CI/CD Contract Gating CLI.
Executes automated pre-merge gating for Pull Requests:
Contract Validation -> Schema Diff -> Data Quality Regression -> Merge Verdict (SAFE/WARNING/BREAKING).
Exits with 0 (Allow Merge) or 1 (Block Merge).
"""

import os
import sys
import yaml
import argparse
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

# Reconfigure stdout/stderr for unicode emojis on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataguard.ci.gate import CICDContractGatingEngine
from dataguard.ci.models import GatingVerdict, PRGatingSummary


def get_git_modified_contracts(base_ref: str, contracts_dir: Path) -> List[str]:
    """Finds modified or added contract YAML files compared to base ref."""
    try:
        # Check diff against base_ref
        cmd = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        files = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        contract_files = [f for f in files if "dataguard/contracts/" in f.replace("\\", "/") and f.endswith((".yaml", ".yml"))]
        if contract_files:
            return contract_files
    except Exception:
        pass

    # Fallback to local uncommitted git status
    try:
        cmd = ["git", "status", "--porcelain"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        files = []
        for line in res.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                f = parts[-1]
                if "dataguard/contracts/" in f.replace("\\", "/") and f.endswith((".yaml", ".yml")):
                    files.append(f)
        if files:
            return files
    except Exception:
        pass

    return []


def load_baseline_yaml(file_path: str, base_ref: str) -> Optional[Dict[str, Any]]:
    """Loads contract content from git base_ref (e.g. origin/main:path)."""
    norm_path = file_path.replace("\\", "/")
    try:
        cmd = ["git", "show", f"{base_ref}:{norm_path}"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return yaml.safe_load(res.stdout)
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="DataGuard CI/CD Pull Request Schema Compatibility Gate")
    parser.add_argument("--base", default="origin/main", help="Base git ref to compare against (default: origin/main)")
    parser.add_argument("--contracts-dir", default="dataguard/contracts", help="Path to contracts directory")
    parser.add_argument("--all", action="store_true", help="Analyze all contracts against base ref")
    parser.add_argument("--files", nargs="*", help="Specific contract files to analyze")
    parser.add_argument("--output-summary", help="Path to write GitHub Step Summary markdown")
    parser.add_argument("--allow-breaking", action="store_true", help="Admin override: do not exit with 1 on breaking changes")
    parser.add_argument("--skip-quality", action="store_true", help="Skip Great Expectations sample quality regression check")

    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent
    contracts_dir = root_dir / args.contracts_dir

    print("=" * 75)
    print("DATAGUARD CI/CD SCHEMA COMPATIBILITY & QUALITY GATING")
    print("=" * 75)
    print(f"Base Target Ref : {args.base}")
    print(f"Contracts Dir   : {contracts_dir}")
    print(f"Allow Breaking  : {args.allow_breaking}")
    print("-" * 75)

    # Determine files to inspect
    if args.files:
        target_files = args.files
    elif args.all:
        target_files = [str(p.relative_to(root_dir)) for p in contracts_dir.glob("*.yaml")]
    else:
        target_files = get_git_modified_contracts(args.base, contracts_dir)
        if not target_files:
            print("No modified contracts detected via git diff. Evaluating all contracts in directory...")
            target_files = [str(p.relative_to(root_dir)) for p in contracts_dir.glob("*.yaml")]

    print(f"Evaluating {len(target_files)} contract(s)...")

    contracts_to_evaluate: List[Tuple[Optional[Dict[str, Any]], Dict[str, Any], str]] = []

    for rel_path in target_files:
        full_path = root_dir / rel_path
        if not full_path.exists():
            continue

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                target_dict = yaml.safe_load(f)
        except Exception as e:
            print(f"ERROR: Could not parse target YAML {rel_path}: {e}")
            sys.exit(1)

        baseline_dict = load_baseline_yaml(rel_path, args.base)
        contracts_to_evaluate.append((baseline_dict, target_dict, rel_path))

    # Run Gating Evaluation
    summary: PRGatingSummary = CICDContractGatingEngine.evaluate_pr(
        contracts_to_evaluate=contracts_to_evaluate,
        allow_breaking=args.allow_breaking,
        validate_quality=not args.skip_quality
    )

    # Output Terminal Summary
    print("\n" + summary.markdown_report)
    print("\n" + "=" * 75)

    # Write GitHub Step Summary if requested or environment variable is set
    summary_path = args.output_summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(summary.markdown_report + "\n")
            print(f"Wrote summary report to: {summary_path}")
        except Exception as e:
            print(f"WARNING: Could not write GitHub Step Summary: {e}")

    # Verdict Statement
    if summary.can_merge:
        print(f"\n[CI RESULT: {summary.verdict.value}] MERGE ALLOWED ✅ (Exit Code: {summary.exit_code})")
    else:
        print(f"\n[CI RESULT: {summary.verdict.value}] MERGE BLOCKED ❌ (Exit Code: {summary.exit_code})")
        print("Please resolve the breaking changes listed above or seek administrative override.")

    sys.exit(summary.exit_code)


if __name__ == "__main__":
    main()

"""
DataGuard CLI Script: Register Contracts
Scans dataguard/contracts/*.yaml, parses YAML, validates schema, and registers contracts into PostgreSQL registry.
"""

import sys
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dataguard.contracts.registry import ContractRegistryService, ContractValidationError, DuplicateVersionError

CONTRACTS_DIR = BASE_DIR / "dataguard" / "contracts"

def register_all_contracts():
    print("============================================================")
    print("  DATAGUARD CONTRACT REGISTRATION PROCESSOR")
    print("============================================================")
    
    registry = ContractRegistryService()
    print(f"Target Database : {registry.get_db_engine_name().upper()} ({registry.db_url.split('@')[-1] if '@' in registry.db_url else registry.db_url})")
    files = list(CONTRACTS_DIR.glob("*.yaml"))
    
    registered_count = 0
    skipped_count = 0
    failed_count = 0
    failures = []

    print(f"Discovered {len(files)} contract files in {CONTRACTS_DIR}\n")

    for p in sorted(files):
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
                contract_dict = yaml.safe_load(content)

            result = registry.register_contract(
                contract=contract_dict,
                yaml_content=content,
                created_by="cli-register",
                allow_skip=True
            )

            if result.get("status") == "REGISTERED":
                registered_count += 1
                print(f" [REGISTERED] {result['dataset']} ({result['version']})")
            elif result.get("status") == "SKIPPED":
                skipped_count += 1
                print(f" [SKIPPED]    {result['dataset']} ({result['version']}) - {result.get('reason')}")
            else:
                registered_count += 1

        except ContractValidationError as e:
            failed_count += 1
            failures.append((p.name, str(e)))
            print(f" [FAILED]     {p.name}: {e}")
        except DuplicateVersionError as e:
            skipped_count += 1
            print(f" [SKIPPED]    {p.name}: {e}")
        except Exception as e:
            failed_count += 1
            failures.append((p.name, str(e)))
            print(f" [ERROR]      {p.name}: {e}")

    print("\n------------------------------------------------------------")
    print("REGISTRATION SUMMARY")
    print("------------------------------------------------------------")
    print(f"Registered: {registered_count}")
    print(f"Skipped:    {skipped_count}")
    print(f"Failed:     {failed_count}")
    print("============================================================\n")

    if failed_count > 0:
        print("Failure Details:")
        for fname, err in failures:
            print(f"  - {fname}: {err}")
        sys.exit(1)

if __name__ == "__main__":
    register_all_contracts()

"""
DataGuard CLI Script: List Registered Contracts
Lists datasets, latest versions, owners, statuses, and SLAs from DataGuard persistent registry.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dataguard.contracts.registry import ContractRegistryService

def list_registered_contracts():
    registry = ContractRegistryService()
    contracts = registry.list_contracts()

    print("==========================================================================================")
    print("  DATAGUARD CONTRACT REGISTRY CATALOG")
    print("==========================================================================================")
    print(f"{'Dataset Name':<32} | {'Version':<8} | {'Owner':<22} | {'Status':<10} | {'SLA (m)':<7}")
    print("-" * 90)

    for c in contracts:
        print(f"{c['dataset']:<32} | {c['version']:<8} | {c['owner']:<22} | {c['status']:<10} | {c['freshness_sla_minutes']:<7}")

    print("==========================================================================================")
    print(f"Total Registered Datasets: {len(contracts)}\n")

if __name__ == "__main__":
    list_registered_contracts()

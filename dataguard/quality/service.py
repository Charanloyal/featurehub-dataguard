"""
DataGuard Data Quality Validation Service.
Integrates Great Expectations validation runner with DataGuard platform components.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from dataguard.quality.runner import DataQualityRunner
from dataguard.quality.result_store import QualityResultStore
from dataguard.contracts.registry import ContractRegistryService


class DataQualityEngine:
    """
    Main entry point for DataGuard data quality operations.
    Delegates to DataQualityRunner backed by Great Expectations and PostgreSQL.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        db_url: Optional[str] = None,
        runner: Optional[DataQualityRunner] = None
    ):
        if runner:
            self.runner = runner
        else:
            registry = ContractRegistryService(db_path=db_path, db_url=db_url)
            store = QualityResultStore(db_path=db_path, db_url=db_url)
            self.runner = DataQualityRunner(registry_service=registry, result_store=store)

    def validate_dataset(
        self,
        dataset_name: str,
        df: Optional[pd.DataFrame] = None,
        contract: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        pipeline: str = "default_pipeline"
    ) -> Any:
        """
        Executes Great Expectations quality validation suite against the dataset.
        Returns a rich QualityRunResult supporting both model attribute and dictionary access.
        """
        return self.runner.run_validation(
            dataset_name=dataset_name,
            df=df,
            version=version,
            contract=contract,
            pipeline=pipeline
        )

    def get_latest_run(self, dataset_name: str) -> Optional[Any]:
        """Retrieves the most recent quality validation run for a dataset."""
        return self.runner.result_store.get_latest_run(dataset_name)

    def get_history(self, dataset_name: str, limit: int = 20) -> List[Any]:
        """Retrieves historical validation runs for a dataset."""
        return self.runner.result_store.get_history(dataset_name, limit=limit)

    def get_run(self, run_id: str) -> Optional[Any]:
        """Retrieves a specific validation run by run_id."""
        return self.runner.result_store.get_run(run_id)

    def list_results(
        self,
        dataset: Optional[str] = None,
        status: Optional[str] = None,
        pipeline: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Queries individual check results with filtering."""
        return self.runner.result_store.list_results(
            dataset=dataset,
            status=status,
            pipeline=pipeline,
            limit=limit
        )

    def get_summary(self) -> Any:
        """Dynamically computes system-wide quality summary."""
        total_registered = len(self.runner.registry.list_contracts())
        return self.runner.result_store.get_summary(total_registered_datasets=total_registered)

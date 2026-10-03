"""
DataGuard Airflow Plugin (Phase G).
Registers DataGuard operators and hooks inside Apache Airflow.
"""

from datetime import timedelta
from typing import Dict, Any, Optional

try:
    from airflow.plugins_manager import AirflowPlugin
    from airflow.models.baseoperator import BaseOperator
except ImportError:
    class AirflowPlugin:
        pass
    from pipelines.airflow.shim import BaseOperator

from dataguard.pipelines.runner import DataGuardPipelineOrchestrator


class DataGuardQualityOperator(BaseOperator):
    """
    Airflow Operator that orchestrates a complete DataGuard quality, schema,
    OpenLineage, and incident workflow.
    """

    template_fields = ("pipeline_id", "dataset_name", "test_scenario")

    def __init__(
        self,
        pipeline_id: str,
        dataset_name: Optional[str] = None,
        test_scenario: Optional[str] = None,
        timeout_seconds: float = 60.0,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.pipeline_id = pipeline_id
        self.dataset_name = dataset_name
        self.test_scenario = test_scenario
        self.timeout_seconds = timeout_seconds

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        ti = context.get("task_instance")
        run_id = getattr(ti, "run_id", None) if ti else None

        orchestrator = DataGuardPipelineOrchestrator()
        result = orchestrator.execute_pipeline(
            pipeline_id=self.pipeline_id,
            dataset_name=self.dataset_name,
            run_id=run_id,
            test_scenario=self.test_scenario,
            timeout_seconds=self.timeout_seconds,
            raise_on_failure=True
        )
        return result


class DataGuardPlugin(AirflowPlugin):
    name = "dataguard_plugin"
    operators = [DataGuardQualityOperator]

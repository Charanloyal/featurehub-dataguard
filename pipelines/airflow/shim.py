"""
Lightweight Airflow Compatibility Shim for Offline Environments.
Allows DAG definition, parsing, task dependency inspection, and structural validation
without requiring a full Apache Airflow installation on platforms like Windows.
When native apache-airflow is present, native classes are used instead.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable


class TaskInstanceShim:
    def __init__(self, task_id: str, dag_id: str, execution_date: Optional[datetime] = None):
        self.task_id = task_id
        self.dag_id = dag_id
        self.execution_date = execution_date or datetime.now()
        self.xcom_data: Dict[str, Any] = {}

    def xcom_push(self, key: str, value: Any):
        self.xcom_data[key] = value

    def xcom_pull(self, task_ids: Optional[str] = None, key: Optional[str] = None) -> Any:
        return self.xcom_data.get(key) if key else self.xcom_data


class BaseOperatorShim:
    def __init__(
        self,
        task_id: str,
        dag: Optional['DAGShim'] = None,
        retries: int = 0,
        retry_delay: Optional[timedelta] = None,
        execution_timeout: Optional[timedelta] = None,
        on_failure_callback: Optional[Callable] = None,
        **kwargs
    ):
        self.task_id = task_id
        self.retries = retries
        self.retry_delay = retry_delay or timedelta(minutes=1)
        self.execution_timeout = execution_timeout
        self.on_failure_callback = on_failure_callback
        self.upstream_list: List['BaseOperatorShim'] = []
        self.downstream_list: List['BaseOperatorShim'] = []
        self.kwargs = kwargs

        active_dag = dag or DAGShim._current_dag
        self.dag = active_dag
        if active_dag is not None:
            active_dag.add_task(self)

    def set_downstream(self, other):
        if isinstance(other, (list, tuple, set)):
            for o in other:
                self.set_downstream(o)
            return other
        if other not in self.downstream_list:
            self.downstream_list.append(other)
        if self not in other.upstream_list:
            other.upstream_list.append(self)
        return other

    def set_upstream(self, other):
        if isinstance(other, (list, tuple, set)):
            for o in other:
                self.set_upstream(o)
            return other
        if other not in self.upstream_list:
            self.upstream_list.append(other)
        if self not in other.downstream_list:
            other.downstream_list.append(self)
        return other

    def __rshift__(self, other):
        return self.set_downstream(other)

    def __lshift__(self, other):
        return self.set_upstream(other)

    def __rrshift__(self, other):
        """Supports [op1, op2] >> op3"""
        if isinstance(other, (list, tuple, set)):
            for o in other:
                if hasattr(o, "set_downstream"):
                    o.set_downstream(self)
            return self
        return self.set_upstream(other)

    def __rlshift__(self, other):
        """Supports [op1, op2] << op3"""
        if isinstance(other, (list, tuple, set)):
            for o in other:
                if hasattr(o, "set_upstream"):
                    o.set_upstream(self)
            return self
        return self.set_downstream(other)

    def execute(self, context: Dict[str, Any]) -> Any:
        return None


class PythonOperatorShim(BaseOperatorShim):
    def __init__(
        self,
        task_id: str,
        python_callable: Callable,
        op_kwargs: Optional[Dict[str, Any]] = None,
        op_args: Optional[List[Any]] = None,
        provide_context: bool = True,
        dag: Optional['DAGShim'] = None,
        **kwargs
    ):
        super().__init__(task_id=task_id, dag=dag, **kwargs)
        self.python_callable = python_callable
        self.op_kwargs = op_kwargs or {}
        self.op_args = op_args or []
        self.provide_context = provide_context

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Any:
        ctx = context or {"task_instance": TaskInstanceShim(self.task_id, self.dag.dag_id if self.dag else "dag")}
        kwargs = dict(self.op_kwargs)
        if self.provide_context:
            kwargs.update(ctx)
        return self.python_callable(*self.op_args, **kwargs)


class EmptyOperatorShim(BaseOperatorShim):
    pass


class DAGShim:
    _current_dag: Optional['DAGShim'] = None

    def __init__(
        self,
        dag_id: str,
        description: Optional[str] = None,
        schedule_interval: Optional[str] = None,
        schedule: Optional[str] = None,
        start_date: Optional[datetime] = None,
        default_args: Optional[Dict[str, Any]] = None,
        catchup: bool = False,
        tags: Optional[List[str]] = None,
        **kwargs
    ):
        self.dag_id = dag_id
        self.description = description
        self.schedule_interval = schedule_interval or schedule
        self.start_date = start_date or datetime(2026, 1, 1)
        self.default_args = default_args or {}
        self.catchup = catchup
        self.tags = tags or []
        self._tasks: Dict[str, BaseOperatorShim] = {}
        self.kwargs = kwargs

    def add_task(self, task: BaseOperatorShim):
        self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> BaseOperatorShim:
        return self._tasks[task_id]

    @property
    def task_dict(self) -> Dict[str, BaseOperatorShim]:
        return self._tasks

    @property
    def tasks(self) -> List[BaseOperatorShim]:
        return list(self._tasks.values())

    @property
    def task_ids(self) -> List[str]:
        return list(self._tasks.keys())

    def __enter__(self):
        DAGShim._current_dag = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        DAGShim._current_dag = None


# Aliases
DAG = DAGShim
BaseOperator = BaseOperatorShim
PythonOperator = PythonOperatorShim
EmptyOperator = EmptyOperatorShim
DummyOperator = EmptyOperatorShim

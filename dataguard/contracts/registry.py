"""
DataGuard Persistent Contract Registry Service
Handles contract registration, versioning, discovery, validation, and storage.
Backed by PostgreSQL container infrastructure with explicit SQLite support for unit testing.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    select,
    insert,
    update,
    func,
    and_,
    text
)
from sqlalchemy.engine import Engine

from dataguard.contracts.validator import ContractValidator, ContractValidationError
from dataguard.metrics import (
    CONTRACTS_REGISTERED_TOTAL,
    CONTRACT_REGISTRATION_FAILURES_TOTAL,
    CONTRACT_VALIDATION_TOTAL
)

class DuplicateVersionError(Exception):
    """Raised when registering a version that already exists for a dataset."""
    pass

class ContractNotFoundError(Exception):
    """Raised when a contract or contract version is not found in the registry."""
    pass


def get_default_db_url() -> str:
    """
    Resolves the PostgreSQL connection URL from environment variables.
    Never hardcodes credentials; reads DATABASE_URL or individual POSTGRES_* vars.
    """
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    if os.getenv("DATAGUARD_DB_URL"):
        return os.getenv("DATAGUARD_DB_URL")

    user = os.getenv("POSTGRES_USER", "platform_admin")
    password = os.getenv("POSTGRES_PASSWORD", "platform_secure_pass")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "featurehub_dataguard")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def create_db_engine(db_url: str) -> Engine:
    """
    Creates a SQLAlchemy engine, with automatic driver resolution
    between psycopg2 and pg8000 for maximum platform compatibility (Windows/Linux/Docker).
    """
    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        try:
            import psycopg2  # noqa: F401
            engine = create_engine(db_url, pool_pre_ping=True)
            with engine.connect() as conn:
                pass
            return engine
        except Exception:
            # Fall back to pure-Python pg8000 driver (handles Windows AppLocker/DLL policies)
            pg8000_url = db_url.replace("postgresql://", "postgresql+pg8000://", 1).replace("postgres://", "postgresql+pg8000://", 1)
            return create_engine(pg8000_url, pool_pre_ping=True)

    return create_engine(db_url)


class ContractRegistryService:
    def __init__(
        self, 
        db_url: Optional[str] = None, 
        db_path: Optional[Path] = None,
        engine: Optional[Engine] = None
    ):
        """
        Initializes the Contract Registry service.
        In production, connects to PostgreSQL via environment-driven DATABASE_URL.
        In unit tests, an explicit SQLite db_path or db_url can be passed.
        """
        if engine is not None:
            self.engine = engine
            self.db_url = str(engine.url)
        elif db_url is not None:
            self.db_url = db_url
            self.engine = create_db_engine(self.db_url)
        elif db_path is not None:
            # Explicit SQLite path for unit tests
            self.db_url = f"sqlite:///{Path(db_path).resolve().as_posix()}"
            self.engine = create_engine(self.db_url)
        else:
            # Production: environment-driven PostgreSQL
            self.db_url = get_default_db_url()
            self.engine = create_db_engine(self.db_url)

        self.metadata = MetaData()
        self._define_schema()
        self._init_db()

    def _define_schema(self):
        self.contract_registry = Table(
            "contract_registry",
            self.metadata,
            Column("dataset_name", String(128), primary_key=True),
            Column("latest_version", String(64), nullable=False),
            Column("owner", String(128), nullable=False),
            Column("description", Text),
            Column("freshness_sla_minutes", Integer),
            Column("status", String(32), default="ACTIVE"),
            Column("created_at", DateTime(timezone=True), server_default=func.now()),
            Column("updated_at", DateTime(timezone=True), server_default=func.now()),
        )

        self.contract_versions = Table(
            "contract_versions",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("dataset_name", String(128), ForeignKey("contract_registry.dataset_name", ondelete="CASCADE"), nullable=False),
            Column("version", String(64), nullable=False),
            Column("owner", String(128), nullable=False),
            Column("description", Text),
            Column("freshness_sla_minutes", Integer),
            Column("status", String(32), default="ACTIVE"),
            Column("schema_json", Text, nullable=False),
            Column("contract_payload", Text),
            Column("yaml_content", Text),
            Column("created_at", DateTime(timezone=True), server_default=func.now()),
            Column("created_by", String(128), default="data-platform"),
            UniqueConstraint("dataset_name", "version", name="uq_dataset_version"),
        )

        Index("idx_contract_versions_dataset", self.contract_versions.c.dataset_name)

    def _init_db(self):
        """Initializes tables and indexes idempotently."""
        self.metadata.create_all(self.engine)

    def register_contract(
        self, 
        contract: Dict[str, Any], 
        yaml_content: Optional[str] = None, 
        created_by: str = "data-platform",
        allow_skip: bool = False
    ) -> Dict[str, Any]:
        """
        Validates and registers a new contract version into the PostgreSQL registry.
        Maintains parent-child relationship (contract_registry -> contract_versions).
        Rejects duplicate versions with DuplicateVersionError.
        """
        # 1. Structural validation
        is_valid, errors = ContractValidator.validate_contract(contract)
        CONTRACT_VALIDATION_TOTAL.labels(result="pass" if is_valid else "fail").inc()
        if not is_valid:
            CONTRACT_REGISTRATION_FAILURES_TOTAL.inc()
            raise ContractValidationError(f"Invalid contract structure: {'; '.join(errors)}")

        dataset_name = contract["dataset"]
        version = contract["version"]
        owner = contract["owner"]
        description = contract.get("description", "")
        freshness_sla = contract.get("freshness_sla_minutes", 60)
        status = contract.get("status", "ACTIVE")

        schema_json = json.dumps(contract)
        if not yaml_content:
            yaml_content = yaml.dump(contract, sort_keys=False)

        now = datetime.now(timezone.utc)

        with self.engine.begin() as conn:
            # Check duplicate version
            sel_ver = select(self.contract_versions.c.id).where(
                and_(
                    self.contract_versions.c.dataset_name == dataset_name,
                    self.contract_versions.c.version == version
                )
            )
            existing = conn.execute(sel_ver).fetchone()
            if existing:
                if allow_skip:
                    return {
                        "status": "SKIPPED",
                        "dataset": dataset_name,
                        "version": version,
                        "reason": f"Version '{version}' for dataset '{dataset_name}' already registered."
                    }
                CONTRACT_REGISTRATION_FAILURES_TOTAL.inc()
                raise DuplicateVersionError(f"Version '{version}' for dataset '{dataset_name}' already exists.")

            # Upsert dataset into contract_registry
            sel_reg = select(self.contract_registry.c.dataset_name).where(
                self.contract_registry.c.dataset_name == dataset_name
            )
            reg_row = conn.execute(sel_reg).fetchone()

            if reg_row:
                upd = (
                    update(self.contract_registry)
                    .where(self.contract_registry.c.dataset_name == dataset_name)
                    .values(
                        latest_version=version,
                        owner=owner,
                        description=description,
                        freshness_sla_minutes=freshness_sla,
                        status=status,
                        updated_at=now
                    )
                )
                conn.execute(upd)
            else:
                ins = insert(self.contract_registry).values(
                    dataset_name=dataset_name,
                    latest_version=version,
                    owner=owner,
                    description=description,
                    freshness_sla_minutes=freshness_sla,
                    status=status,
                    created_at=now,
                    updated_at=now
                )
                conn.execute(ins)

            # Insert version into contract_versions
            ins_ver = insert(self.contract_versions).values(
                dataset_name=dataset_name,
                version=version,
                owner=owner,
                description=description,
                freshness_sla_minutes=freshness_sla,
                status=status,
                schema_json=schema_json,
                contract_payload=schema_json,
                yaml_content=yaml_content,
                created_at=now,
                created_by=created_by
            )
            conn.execute(ins_ver)

        CONTRACTS_REGISTERED_TOTAL.inc()
        return {
            "status": "REGISTERED",
            "dataset": dataset_name,
            "version": version,
            "owner": owner,
            "contract": contract
        }

    def get_contract(self, dataset_name: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a contract version by dataset_name and optional version string.
        Defaults to latest_version if version is None.
        """
        with self.engine.connect() as conn:
            target_version = version
            if not target_version:
                sel_reg = select(self.contract_registry.c.latest_version).where(
                    self.contract_registry.c.dataset_name == dataset_name
                )
                reg_row = conn.execute(sel_reg).fetchone()
                if not reg_row:
                    return None
                target_version = reg_row[0]

            sel_ver = select(self.contract_versions).where(
                and_(
                    self.contract_versions.c.dataset_name == dataset_name,
                    self.contract_versions.c.version == target_version
                )
            )
            version_row = conn.execute(sel_ver).mappings().fetchone()
            if not version_row:
                return None

            raw_payload = version_row["schema_json"] or version_row["contract_payload"]
            contract_data = json.loads(raw_payload)
            contract_data["registered_id"] = version_row["id"]
            created_at = version_row["created_at"]
            contract_data["created_at"] = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
            contract_data["created_by"] = version_row["created_by"]
            contract_data["yaml_content"] = version_row["yaml_content"]
            return contract_data

    def dataset_exists(self, dataset_name: str) -> bool:
        """Checks if a dataset exists in the contract registry."""
        with self.engine.connect() as conn:
            stmt = select(self.contract_registry.c.dataset_name).where(
                self.contract_registry.c.dataset_name == dataset_name
            )
            return conn.execute(stmt).fetchone() is not None

    def list_contracts(
        self, 
        owner: Optional[str] = None, 
        status: Optional[str] = None, 
        dataset: Optional[str] = None, 
        version: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Lists registered contracts with filtering by owner, status, dataset, version.
        """
        with self.engine.connect() as conn:
            if version:
                stmt = select(self.contract_versions)
                if owner:
                    stmt = stmt.where(self.contract_versions.c.owner == owner)
                if status:
                    stmt = stmt.where(self.contract_versions.c.status == status)
                if dataset:
                    stmt = stmt.where(self.contract_versions.c.dataset_name == dataset)
                stmt = stmt.where(self.contract_versions.c.version == version)

                rows = conn.execute(stmt).mappings().fetchall()
                results = []
                for r in rows:
                    raw_payload = r["schema_json"] or r["contract_payload"]
                    c = json.loads(raw_payload)
                    created_at = r["created_at"]
                    results.append({
                        "dataset": r["dataset_name"],
                        "version": r["version"],
                        "owner": r["owner"],
                        "description": r["description"],
                        "freshness_sla_minutes": r["freshness_sla_minutes"],
                        "status": r["status"],
                        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                        "columns_count": len(c.get("columns", []))
                    })
                return results

            else:
                stmt = select(self.contract_registry)
                if owner:
                    stmt = stmt.where(self.contract_registry.c.owner == owner)
                if status:
                    stmt = stmt.where(self.contract_registry.c.status == status)
                if dataset:
                    stmt = stmt.where(self.contract_registry.c.dataset_name == dataset)

                rows = conn.execute(stmt).mappings().fetchall()
                results = []
                for r in rows:
                    created_at = r["created_at"]
                    updated_at = r["updated_at"]
                    results.append({
                        "dataset": r["dataset_name"],
                        "version": r["latest_version"],
                        "owner": r["owner"],
                        "description": r["description"],
                        "freshness_sla_minutes": r["freshness_sla_minutes"],
                        "status": r["status"],
                        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at)
                    })
                return results

    def get_contract_versions(self, dataset_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all version history for a specified dataset.
        """
        with self.engine.connect() as conn:
            stmt = (
                select(
                    self.contract_versions.c.version,
                    self.contract_versions.c.owner,
                    self.contract_versions.c.description,
                    self.contract_versions.c.status,
                    self.contract_versions.c.freshness_sla_minutes,
                    self.contract_versions.c.created_at,
                    self.contract_versions.c.created_by,
                )
                .where(self.contract_versions.c.dataset_name == dataset_name)
                .order_by(self.contract_versions.c.id.asc())
            )
            rows = conn.execute(stmt).mappings().fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if hasattr(item["created_at"], "isoformat"):
                    item["created_at"] = item["created_at"].isoformat()
                else:
                    item["created_at"] = str(item["created_at"])
                results.append(item)
            return results

    def validate_contract_structure(self, contract: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Delegates validation to Phase A ContractValidator.
        """
        return ContractValidator.validate_contract(contract)

    def get_db_engine_name(self) -> str:
        """Returns the active SQLAlchemy dialect name (e.g. 'postgresql' or 'sqlite')."""
        return self.engine.dialect.name

"""
Feature Registry Service
Manages feature definitions, versions, entity mappings, and metadata database state.
"""

import sqlite3
from typing import List, Optional, Dict, Any
from pathlib import Path

from featurehub.feature_definitions.definitions import FEATURE_CATALOG, FeatureDefinition, get_all_features

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "platform_dev.db"

class FeatureRegistryService:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()
        self._sync_catalog()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_registry (
            feature_name TEXT PRIMARY KEY,
            feature_group TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            data_type TEXT NOT NULL,
            description TEXT,
            source_table TEXT,
            version TEXT DEFAULT 'v1',
            owner TEXT DEFAULT 'fraud-analytics-team',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            freshness_sla_minutes INTEGER DEFAULT 60,
            status TEXT DEFAULT 'ACTIVE'
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_groups (
            group_name TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            description TEXT,
            owner TEXT DEFAULT 'fraud-analytics-team'
        );
        """)
        conn.commit()
        conn.close()

    def _sync_catalog(self):
        """Sync python catalog definitions into database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        for f in FEATURE_CATALOG:
            cursor.execute("""
            INSERT OR REPLACE INTO feature_registry 
            (feature_name, feature_group, entity_type, data_type, description, source_table, version, owner, freshness_sla_minutes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (f.name, f.feature_group, f.entity, f.data_type, f.description, f.source_table, f.version, f.owner, f.freshness_sla_minutes, f.status))
        
        # Insert feature groups
        groups = set((f.feature_group, f.entity) for f in FEATURE_CATALOG)
        for g_name, entity in groups:
            cursor.execute("""
            INSERT OR REPLACE INTO feature_groups (group_name, entity_type, description)
            VALUES (?, ?, ?)
            """, (g_name, entity, f"Feature group containing {g_name} metrics"))

        conn.commit()
        conn.close()

    def list_features(self, entity: Optional[str] = None, group: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM feature_registry WHERE 1=1"
        params = []
        if entity:
            query += " AND entity_type = ?"
            params.append(entity)
        if group:
            query += " AND feature_group = ?"
            params.append(group)
            
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_feature(self, feature_name: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM feature_registry WHERE feature_name = ?", (feature_name,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def register_feature(self, feat: FeatureDefinition) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT OR REPLACE INTO feature_registry 
        (feature_name, feature_group, entity_type, data_type, description, source_table, version, owner, freshness_sla_minutes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (feat.name, feat.feature_group, feat.entity, feat.data_type, feat.description, feat.source_table, feat.version, feat.owner, feat.freshness_sla_minutes, feat.status))
        conn.commit()
        conn.close()
        return feat.dict()

    def list_groups(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM feature_groups")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

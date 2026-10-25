from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import Observation
from .sensors import SENSORS


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sensor_definitions (
    id TEXT PRIMARY KEY,
    group_name TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    instrument TEXT NOT NULL,
    frequency TEXT NOT NULL,
    max_age_days INTEGER NOT NULL,
    primary_source TEXT NOT NULL,
    connected INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    observations_seen INTEGER NOT NULL DEFAULT 0,
    observations_inserted INTEGER NOT NULL DEFAULT 0,
    errors_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS source_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES ingestion_runs(id),
    source_identifier TEXT NOT NULL,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    observations_seen INTEGER NOT NULL DEFAULT 0,
    observations_inserted INTEGER NOT NULL DEFAULT 0,
    detail TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_checks_run_source
ON source_checks(run_id DESC, source_identifier);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id TEXT NOT NULL REFERENCES sensor_definitions(id),
    value REAL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    source_identifier TEXT NOT NULL,
    source_url TEXT NOT NULL,
    as_of TEXT NOT NULL,
    publication_date TEXT,
    retrieved_at TEXT NOT NULL,
    instrument TEXT NOT NULL,
    frequency TEXT NOT NULL,
    quality TEXT NOT NULL,
    data_kind TEXT NOT NULL,
    latency TEXT NOT NULL,
    access TEXT NOT NULL,
    status TEXT NOT NULL,
    methodology TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    UNIQUE(sensor_id, source_identifier, as_of, value)
);

CREATE INDEX IF NOT EXISTS idx_observations_sensor_asof
ON observations(sensor_id, as_of DESC, source_identifier);

CREATE TABLE IF NOT EXISTS source_health (
    source_identifier TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    as_of TEXT NOT NULL,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self._upsert_sensor_definitions()

    def close(self) -> None:
        self.connection.close()

    def _upsert_sensor_definitions(self) -> None:
        for sensor in SENSORS.values():
            self.connection.execute(
                """
                INSERT INTO sensor_definitions
                    (id, group_name, name, unit, instrument, frequency, max_age_days, primary_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    group_name=excluded.group_name,
                    name=excluded.name,
                    unit=excluded.unit,
                    instrument=excluded.instrument,
                    frequency=excluded.frequency,
                    max_age_days=excluded.max_age_days,
                    primary_source=excluded.primary_source
                """,
                (
                    sensor.id, sensor.group, sensor.name, sensor.unit, sensor.instrument,
                    sensor.frequency, sensor.max_age_days, sensor.primary_source,
                ),
            )
        self.connection.commit()

    def begin_run(self, started_at: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO ingestion_runs(started_at, status) VALUES (?, 'running')", (started_at,)
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def record_source_check(
        self, run_id: int, identifier: str, source: str, started_at: str,
        completed_at: str, status: str, seen: int, inserted: int, detail: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO source_checks(
                run_id, source_identifier, source, started_at, completed_at,
                status, observations_seen, observations_inserted, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, identifier, source, started_at, completed_at, status, seen, inserted, detail),
        )
        self.connection.commit()

    def finish_run(
        self, run_id: int, completed_at: str, status: str, seen: int, inserted: int, errors: List[str]
    ) -> None:
        self.connection.execute(
            """
            UPDATE ingestion_runs
            SET completed_at=?, status=?, observations_seen=?, observations_inserted=?, errors_json=?
            WHERE id=?
            """,
            (completed_at, status, seen, inserted, json.dumps(errors, ensure_ascii=False), run_id),
        )
        self.connection.commit()

    def insert_observations(self, observations: Iterable[Observation]) -> int:
        inserted = 0
        touched = set()
        for observation in observations:
            if observation.sensor_id not in SENSORS:
                raise ValueError("Unknown sensor: {}".format(observation.sensor_id))
            existing = self.connection.execute(
                """
                SELECT MAX(revision) AS revision FROM observations
                WHERE sensor_id=? AND source_identifier=? AND as_of=?
                """,
                (observation.sensor_id, observation.source_identifier, observation.as_of),
            ).fetchone()
            revision = int(existing["revision"] or 0) + 1
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO observations (
                    sensor_id, value, unit, source, source_identifier, source_url, as_of,
                    publication_date, retrieved_at, instrument, frequency, quality, data_kind,
                    latency, access, status, methodology, metadata_json, revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.sensor_id, observation.value, observation.unit, observation.source,
                    observation.source_identifier, observation.source_url, observation.as_of,
                    observation.publication_date, observation.retrieved_at, observation.instrument,
                    observation.frequency, observation.quality, observation.data_kind,
                    observation.latency, observation.access, observation.status,
                    observation.methodology, json.dumps(observation.metadata, sort_keys=True), revision,
                ),
            )
            if cursor.rowcount:
                inserted += 1
            touched.add(observation.sensor_id)
        if touched:
            self.connection.executemany(
                "UPDATE sensor_definitions SET connected=1 WHERE id=?",
                [(sensor_id,) for sensor_id in touched],
            )
        self.connection.commit()
        return inserted

    def set_source_health(self, identifier: str, source: str, checked_at: str, status: str, detail: str) -> None:
        self.connection.execute(
            """
            INSERT INTO source_health(source_identifier, source, checked_at, status, detail)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_identifier) DO UPDATE SET
                source=excluded.source,
                checked_at=excluded.checked_at,
                status=excluded.status,
                detail=excluded.detail
            """,
            (identifier, source, checked_at, status, detail),
        )
        self.connection.commit()

    def save_analysis(self, analysis: Dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO analyses(id, mode, as_of, created_at, title, evidence_level, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                created_at=excluded.created_at,
                title=excluded.title,
                evidence_level=excluded.evidence_level,
                payload_json=excluded.payload_json
            """,
            (
                analysis["id"], analysis["mode"], analysis["as_of"], analysis["created_at"],
                analysis["title"], analysis["evidence_level"],
                json.dumps(analysis["payload"], ensure_ascii=False, sort_keys=True),
            ),
        )
        self.connection.commit()

    def observations(
        self, sensor_ids: Optional[List[str]] = None, limit_per_sensor: int = 100,
        primary_only: bool = False,
    ) -> List[Dict[str, Any]]:
        rows: List[sqlite3.Row] = []
        ids = sensor_ids or list(SENSORS)
        for sensor_id in ids:
            source_filter = "AND quality != 'official_crosscheck'" if primary_only else ""
            rows.extend(
                self.connection.execute(
                    """
                    SELECT * FROM observations
                    WHERE sensor_id=? {source_filter}
                    ORDER BY as_of DESC, revision DESC, id DESC
                    LIMIT ?
                    """.format(source_filter=source_filter),
                    (sensor_id, limit_per_sensor),
                ).fetchall()
            )
        return [self._row_to_observation(row) for row in rows]

    def latest(self, sensor_id: str, primary_only: bool = True) -> Optional[Dict[str, Any]]:
        source_filter = "AND quality != 'official_crosscheck'" if primary_only else ""
        row = self.connection.execute(
            """
            SELECT * FROM observations
            WHERE sensor_id=? {source_filter}
            ORDER BY as_of DESC, revision DESC, id DESC LIMIT 1
            """.format(source_filter=source_filter),
            (sensor_id,),
        ).fetchone()
        return self._row_to_observation(row) if row else None

    def latest_by_quality(self, sensor_id: str, quality: str) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            """
            SELECT * FROM observations
            WHERE sensor_id=? AND quality=?
            ORDER BY as_of DESC, revision DESC, id DESC LIMIT 1
            """,
            (sensor_id, quality),
        ).fetchone()
        return self._row_to_observation(row) if row else None

    def observation_at(
        self, sensor_id: str, as_of: str, quality: Optional[str] = None,
        exclude_quality: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        clauses = ["sensor_id=?", "as_of=?"]
        parameters: List[Any] = [sensor_id, as_of]
        if quality is not None:
            clauses.append("quality=?")
            parameters.append(quality)
        if exclude_quality is not None:
            clauses.append("quality!=?")
            parameters.append(exclude_quality)
        row = self.connection.execute(
            "SELECT * FROM observations WHERE {} ORDER BY revision DESC, id DESC LIMIT 1".format(
                " AND ".join(clauses)
            ),
            parameters,
        ).fetchone()
        return self._row_to_observation(row) if row else None

    def coverage(self) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT d.*,
                   COUNT(o.id) AS observation_count,
                   MAX(o.as_of) AS latest_as_of,
                   MAX(o.retrieved_at) AS latest_retrieved_at
            FROM sensor_definitions d
            LEFT JOIN observations o ON o.sensor_id=d.id
            GROUP BY d.id
            ORDER BY d.group_name, d.id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def analyses(self) -> List[Dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM analyses ORDER BY as_of DESC, created_at DESC").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def source_health(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM source_health ORDER BY source_identifier"
        ).fetchall()]

    def recent_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["errors"] = json.loads(item.pop("errors_json"))
            result.append(item)
        return result

    def recent_source_checks(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM source_checks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]

    @staticmethod
    def _row_to_observation(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        return item


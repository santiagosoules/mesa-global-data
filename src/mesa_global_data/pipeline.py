from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .analysis import cot_reconciliation_analysis
from .connectors import cftc, h41, nyfed, ofr, treasury
from .exporter import export_all
from .storage import Storage
from .validation import validate_storage


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connectors(profile: str, current_year: int, started_at: str) -> List[Tuple[str, str, Any]]:
    available: Dict[str, Tuple[str, str, Any]] = {
        "treasury": (
            "treasury", "U.S. Department of the Treasury",
            lambda: treasury.collect(current_year, started_at),
        ),
        "h41": (
            "h41", "Board of Governors of the Federal Reserve System",
            lambda: h41.collect(started_at),
        ),
        "nyfed": (
            "nyfed", "Federal Reserve Bank of New York",
            lambda: nyfed.collect(started_at, "{}-01-01".format(current_year - 1)),
        ),
        "ofr": (
            "ofr", "U.S. Office of Financial Research",
            lambda: ofr.collect(started_at),
        ),
        "cftc": (
            "cftc", "U.S. Commodity Futures Trading Commission",
            lambda: cftc.collect(current_year, started_at),
        ),
    }
    profiles = {
        "daily": ("treasury", "nyfed", "ofr"),
        "h41": ("h41",),
        "weekly": ("cftc",),
        "all": ("treasury", "h41", "nyfed", "ofr", "cftc"),
    }
    if profile not in profiles:
        raise ValueError("Unknown collection profile: {}".format(profile))
    return [available[name] for name in profiles[profile]]


def collect_all(
    db_path: str, export_dir: str, profile: str = "all", started_at: Optional[str] = None,
) -> Dict[str, Any]:
    started_at = started_at or utc_now()
    current_year = datetime.now(timezone.utc).year
    storage = Storage(db_path)
    run_id = storage.begin_run(started_at)
    seen = 0
    inserted = 0
    errors: List[str] = []
    connectors = _connectors(profile, current_year, started_at)
    try:
        for identifier, source, callback in connectors:
            source_started_at = utc_now()
            try:
                observations = callback()
                seen += len(observations)
                source_inserted = storage.insert_observations(observations)
                inserted += source_inserted
                completed_at = utc_now()
                detail = "{} observations parsed; {} new revisions stored".format(
                    len(observations), source_inserted
                )
                storage.set_source_health(identifier, source, completed_at, "ok", detail)
                storage.record_source_check(
                    run_id, identifier, source, source_started_at, completed_at,
                    "ok", len(observations), source_inserted, detail,
                )
            except Exception as exc:
                message = "{}: {}".format(identifier, exc)
                errors.append(message)
                completed_at = utc_now()
                storage.set_source_health(identifier, source, completed_at, "error", str(exc))
                storage.record_source_check(
                    run_id, identifier, source, source_started_at, completed_at,
                    "error", 0, 0, str(exc),
                )
        if storage.latest("nq_cot_leveraged_funds_net"):
            storage.save_analysis(cot_reconciliation_analysis(storage, utc_now()))
        completed_at = utc_now()
        validation = validate_storage(storage, completed_at)
        status = (
            "ok" if not errors and validation["status"] == "ok"
            else "degraded" if errors and validation["blocking_issue_count"] == 0
            else "error"
        )
        storage.finish_run(run_id, completed_at, status, seen, inserted, errors)
        exports = export_all(storage, export_dir, completed_at)
        return {
            "status": status,
            "profile": profile,
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "observations_seen": seen,
            "observations_inserted": inserted,
            "errors": errors,
            "validation": validation,
            "exports": exports,
        }
    except Exception:
        storage.finish_run(run_id, utc_now(), "error", seen, inserted, errors)
        raise
    finally:
        storage.close()


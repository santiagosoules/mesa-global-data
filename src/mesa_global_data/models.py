from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SensorDefinition:
    id: str
    group: str
    name: str
    unit: str
    instrument: str
    frequency: str
    max_age_days: int
    primary_source: str


@dataclass
class Observation:
    sensor_id: str
    value: Optional[float]
    unit: str
    source: str
    source_identifier: str
    source_url: str
    as_of: str
    publication_date: Optional[str]
    retrieved_at: str
    instrument: str
    frequency: str
    quality: str
    data_kind: str = "observed"
    latency: str = "publication"
    access: str = "public"
    status: str = "ok"
    methodology: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


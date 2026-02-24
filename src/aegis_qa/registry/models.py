"""Data models for service health and status."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HealthResult:
    """Result of a single health check."""

    healthy: bool
    status_code: Optional[int] = None
    latency_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class ServiceStatus:
    """Full status of a registered service."""

    key: str
    name: str
    description: str
    url: str
    features: list[str] = field(default_factory=list)
    health: Optional[HealthResult] = None

    @property
    def status_label(self) -> str:
        if self.health is None:
            return "unknown"
        if self.health.healthy:
            return "healthy"
        if self.health.error and "connect" in self.health.error.lower():
            return "unreachable"
        return "unhealthy"

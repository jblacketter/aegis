"""Data models for service health and status."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HealthResult:
    """Result of a single health check."""

    healthy: bool
    status_code: int | None = None
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class ServiceStatus:
    """Full status of a registered service."""

    key: str
    name: str
    description: str
    url: str
    features: list[str] = field(default_factory=list)
    health: HealthResult | None = None

    @property
    def status_label(self) -> str:
        if self.health is None:
            return "unknown"
        if self.health.healthy:
            return "healthy"
        if self.health.error and "connect" in self.health.error.lower():
            return "unreachable"
        return "unhealthy"

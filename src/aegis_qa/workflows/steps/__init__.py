"""Workflow step implementations."""

from __future__ import annotations

from aegis_qa.workflows.steps.base import BaseStep
from aegis_qa.workflows.steps.discover import DiscoverStep
from aegis_qa.workflows.steps.report import ReportStep
from aegis_qa.workflows.steps.submit_bugs import SubmitBugsStep
from aegis_qa.workflows.steps.test import RunTestsStep
from aegis_qa.workflows.steps.verify import VerifyStep

STEP_REGISTRY: dict[str, type[BaseStep]] = {
    "discover": DiscoverStep,
    "test": RunTestsStep,
    "submit_bugs": SubmitBugsStep,
    "verify": VerifyStep,
    "report": ReportStep,
}

__all__ = ["STEP_REGISTRY", "BaseStep"]

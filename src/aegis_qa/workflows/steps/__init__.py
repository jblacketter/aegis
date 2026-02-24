"""Workflow step implementations."""

from __future__ import annotations

from typing import Dict, Type

from aegis_qa.workflows.steps.discover import DiscoverStep
from aegis_qa.workflows.steps.test import RunTestsStep
from aegis_qa.workflows.steps.submit_bugs import SubmitBugsStep
from aegis_qa.workflows.steps.verify import VerifyStep

from aegis_qa.workflows.steps.base import BaseStep

STEP_REGISTRY: Dict[str, Type[BaseStep]] = {
    "discover": DiscoverStep,
    "test": RunTestsStep,
    "submit_bugs": SubmitBugsStep,
    "verify": VerifyStep,
}

__all__ = ["STEP_REGISTRY", "BaseStep"]

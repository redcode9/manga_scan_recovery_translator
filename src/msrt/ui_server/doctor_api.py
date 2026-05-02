"""Thin wrapper that converts ``run_doctor`` results into UI events.

The pipeline already has a structured ``DoctorCheck`` dataclass; we
just remap it to a Pydantic model that the UI can consume without
needing to understand the dataclass shape.
"""

from __future__ import annotations

from typing import Literal

from msrt.config import Settings
from msrt.doctor import run_doctor
from msrt.ui_server.schemas import DoctorCheckView, DoctorReport

_OverallStatus = Literal["ok", "warn", "fail"]


def build_doctor_report(*, model: str | None = None) -> DoctorReport:
    """Run the full ``msrt doctor`` checklist (no paid smoke) and
    package the result for the UI. Side-effect free apart from
    reading env / disk / process state."""

    effective_model = model or Settings().default_model
    checks = run_doctor(model=effective_model, paid_smoke=False, verbose=False)
    views = [
        DoctorCheckView(
            name=check.name,
            status=check.status,
            message=check.message,
            detail=getattr(check, "detail", None),
        )
        for check in checks
    ]
    return DoctorReport(checks=views, overall_status=_overall(views))


def _overall(views: list[DoctorCheckView]) -> _OverallStatus:
    if any(v.status == "fail" for v in views):
        return "fail"
    if any(v.status == "warn" for v in views):
        return "warn"
    return "ok"

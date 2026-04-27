"""
Module 1 extraction flow built on top of the lightweight AgentController.
Phase 2 keeps the public /testplan/extract API shape stable while adding run/step/artifact tracking.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent, RunContext, AgentRun
from app.services.testplan_service import TestPlanService


class Module1InputResolverAgent(BaseAgent):
    agent_name = "input_resolver"

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            artifacts=[
                {
                    "type": "source_pdf",
                    "summary": {
                        "file_id": payload.get("file_id"),
                        "pages": payload.get("pages") or "ALL",
                        "max_workers": payload.get("max_workers"),
                    },
                }
            ],
        )


class Module1ExtractionAgent(BaseAgent):
    agent_name = "testplan_extractor"

    def __init__(self, service: TestPlanService) -> None:
        self.service = service

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        result = self.service.extract_from_pdf(
            pdf_path=payload["pdf_path"],
            pages=payload.get("pages"),
            max_workers=payload.get("max_workers", 5),
        )
        result_data = result.model_dump()
        status = "completed" if result.status == "success" else "failed"
        errors = list(result.errors or [])
        warnings = list(result.warnings or [])
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            output={"extraction_result": result_data},
            warnings=warnings,
            errors=errors,
            artifacts=[
                {
                    "type": "testplan_result",
                    "summary": {
                        "chip_name": result.chip_name,
                        "chip_type": result.chip_type,
                        "total_params": result.total_params,
                        "pin_count": len(result.pin_definitions),
                    },
                }
            ],
            metadata={
                "http_code": 200 if result.status == "success" else 500,
                "failure_kind": "extraction_failed" if result.status != "success" else None,
            },
        )


def build_module1_extract_controller(*, service: TestPlanService) -> AgentController:
    controller = AgentController()
    controller.register_flow(
        "module1_extract",
        [
            Module1InputResolverAgent(),
            Module1ExtractionAgent(service),
        ],
    )
    return controller


def finalize_module1_run(run, file_id: str) -> Dict[str, Any]:
    result = dict(run.shared.get("extraction_result") or {})
    if not result:
        return {}

    pin_definitions = result.get("pin_definitions") or []
    range_recommendations = result.get("range_recommendations") or []

    return {
        "chip_name": result.get("chip_name", ""),
        "chip_type": result.get("chip_type", "UNKNOWN"),
        "test_scenario": result.get("test_scenario", "GENERAL"),
        "pin_count": len(pin_definitions),
        "statistics": {
            "total": result.get("total_params", 0),
            "A_class": result.get("a_params", 0),
            "B_class": result.get("b_params", 0),
            "C_class": result.get("c_params", 0),
            "blocked": result.get("blocked_params", 0),
            "dc_items": result.get("dc_test_items", 0),
            "ac_items": result.get("ac_test_items", 0),
            "ldo_items": result.get("ldo_test_items", 0),
        },
        "files": {
            "excel": f"/api/v1/testplan/download/{file_id}/excel",
            "json": f"/api/v1/testplan/download/{file_id}/json",
        },
        "sts_compatibility": result.get("sts_compatibility") or {},
        "warnings": list(result.get("warnings") or [])[:5],
        "range_recommendations": range_recommendations,
        "pin_definitions": pin_definitions[:50],
        "run": {
            "run_id": run.run_id,
            "flow_name": run.flow_name,
            "status": run.status,
            "steps": run.steps,
            "warnings": run.warnings,
            "errors": run.errors,
            "artifacts": run.artifacts,
        },
    }


def materialize_module1_run_from_result(
    *,
    file_id: str,
    pages: str | None,
    max_workers: int,
    result_data: Dict[str, Any],
    status: str = "completed",
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> AgentRun:
    timestamp = datetime.now().isoformat()
    pin_definitions = list(result_data.get("pin_definitions") or [])
    steps = [
        {
            "agent": "input_resolver",
            "status": "completed",
            "warnings": [],
            "errors": [],
            "artifacts": [
                {
                    "type": "source_pdf",
                    "summary": {
                        "file_id": file_id,
                        "pages": pages or "ALL",
                        "max_workers": max_workers,
                    },
                }
            ],
            "metadata": {},
        },
        {
            "agent": "testplan_extractor",
            "status": status,
            "warnings": list(warnings or []),
            "errors": list(errors or []),
            "artifacts": [
                {
                    "type": "testplan_result",
                    "summary": {
                        "chip_name": result_data.get("chip_name", ""),
                        "chip_type": result_data.get("chip_type", "UNKNOWN"),
                        "total_params": result_data.get("total_params", 0),
                        "pin_count": len(pin_definitions),
                    },
                }
            ],
            "metadata": {
                "http_code": 200 if status == "completed" else 500,
                "failure_kind": "extraction_failed" if status != "completed" else None,
            },
        },
    ]
    artifacts = [artifact for step in steps for artifact in step.get("artifacts", [])]
    return AgentRun(
        run_id=f"module1_extract_{uuid4().hex[:8]}",
        flow_name="module1_extract",
        status=status,
        created_at=timestamp,
        updated_at=timestamp,
        input_payload={
            "file_id": file_id,
            "pages": pages,
            "max_workers": max_workers,
        },
        steps=steps,
        artifacts=artifacts,
        warnings=list(dict.fromkeys(warnings or [])),
        errors=list(dict.fromkeys(errors or [])),
        shared={"extraction_result": result_data},
    )

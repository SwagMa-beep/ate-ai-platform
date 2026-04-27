"""
Module 2 resource-mapping flow built on top of the lightweight AgentController.
Phase 2 keeps the public /resource-map/generate API shape stable while adding run/step/artifact tracking.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

import pandas as pd

from app.services.agent_controller import AgentController, AgentStepResult, AgentRun, BaseAgent, RunContext
from app.services.resource_mapping_service import ResourceMappingService


class Module2InputResolverAgent(BaseAgent):
    agent_name = "mapping_input_resolver"

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            artifacts=[
                {
                    "type": "mapping_input",
                    "summary": {
                        "file_id": payload.get("file_id"),
                        "chip_type": payload.get("chip_type"),
                        "dual_site": payload.get("dual_site", False),
                    },
                }
            ],
        )


class Module2ResourceMappingAgent(BaseAgent):
    agent_name = "resource_mapper"

    def __init__(self, service: ResourceMappingService) -> None:
        self.service = service

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        result = self.service.generate_resource_map(
            payload["extraction_result"],
            payload["pin_mapping_df"],
            payload.get("dual_site", False),
        )
        result_data = result.model_dump()
        status = "completed" if result.status == "success" else "failed"
        errors = list(result.errors or [])
        warnings = list(result.warnings or [])
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            output={"resource_map_result": result_data},
            warnings=warnings,
            errors=errors,
            artifacts=[
                {
                    "type": "resource_mapping",
                    "summary": {
                        "chip_name": result.chip_name,
                        "chip_type": result.chip_type,
                        "adapter_model": result.adapter_model,
                        "mapping_count": len(result.resource_mappings),
                        "pgs_items": len(result.pgs_configs),
                    },
                }
            ],
            metadata={
                "http_code": 200 if result.status == "success" else 500,
                "failure_kind": "resource_mapping_failed" if result.status != "success" else None,
            },
        )


def build_module2_resource_map_controller(*, service: ResourceMappingService) -> AgentController:
    controller = AgentController()
    controller.register_flow(
        "module2_resource_map",
        [
            Module2InputResolverAgent(),
            Module2ResourceMappingAgent(service),
        ],
    )
    return controller


def materialize_module2_run_from_result(
    *,
    file_id: str,
    chip_type: str,
    dual_site: bool,
    result_data: Dict[str, Any],
    status: str = "completed",
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> AgentRun:
    timestamp = datetime.now().isoformat()
    steps = [
        {
            "agent": "mapping_input_resolver",
            "status": "completed",
            "warnings": [],
            "errors": [],
            "artifacts": [
                {
                    "type": "mapping_input",
                    "summary": {
                        "file_id": file_id,
                        "chip_type": chip_type,
                        "dual_site": dual_site,
                    },
                }
            ],
            "metadata": {},
        },
        {
            "agent": "resource_mapper",
            "status": status,
            "warnings": list(warnings or []),
            "errors": list(errors or []),
            "artifacts": [
                {
                    "type": "resource_mapping",
                    "summary": {
                        "chip_name": result_data.get("chip_name", ""),
                        "chip_type": result_data.get("chip_type", chip_type),
                        "adapter_model": result_data.get("adapter_model", ""),
                        "mapping_count": len(result_data.get("resource_mappings") or []),
                        "pgs_items": len(result_data.get("pgs_configs") or []),
                    },
                }
            ],
            "metadata": {
                "http_code": 200 if status == "completed" else 500,
                "failure_kind": "resource_mapping_failed" if status != "completed" else None,
            },
        },
    ]
    artifacts = [artifact for step in steps for artifact in step.get("artifacts", [])]
    return AgentRun(
        run_id=f"module2_resource_map_{uuid4().hex[:8]}",
        flow_name="module2_resource_map",
        status=status,
        created_at=timestamp,
        updated_at=timestamp,
        input_payload={
            "file_id": file_id,
            "chip_type": chip_type,
            "dual_site": dual_site,
        },
        steps=steps,
        artifacts=artifacts,
        warnings=list(dict.fromkeys(warnings or [])),
        errors=list(dict.fromkeys(errors or [])),
        shared={"resource_map_result": result_data},
    )


def finalize_module2_run(
    run: AgentRun,
    *,
    chip_name: str,
    out_prefix: str,
    pin_auto_loaded: bool,
    summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    result = dict(run.shared.get("resource_map_result") or {})
    if not result:
        return {}

    return {
        "chip_name": chip_name,
        "chip_type": result.get("chip_type", "UNKNOWN"),
        "adapter": result.get("adapter_model", ""),
        "pin_count": len(result.get("resource_mappings") or []),
        "pgs_items": len(result.get("pgs_configs") or []),
        "pin_auto_loaded": pin_auto_loaded,
        "download": {
            "resource_map_excel": f"/api/v1/resource-map/download/{out_prefix}/excel",
            "schematic_svg": f"/api/v1/resource-map/download/{out_prefix}/svg",
            "bom_excel": f"/api/v1/resource-map/download/{out_prefix}/bom",
        },
        "warnings": list(result.get("warnings") or []),
        "summary": summary or {},
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

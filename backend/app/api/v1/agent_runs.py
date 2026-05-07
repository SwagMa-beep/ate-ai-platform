"""Unified run-query endpoints for lightweight agent flows."""
from __future__ import annotations

from datetime import datetime
from threading import Thread
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.api.v1.codegen import CodegenRequest, run_codegen_flow
from app.core.response import error, paginate, success
from app.flows.full_ate_development_flow import build_full_ate_development_controller
from app.flows.post_review_delivery_flow import build_post_review_delivery_controller
from app.flows.post_review_revision_flow import build_post_review_revision_controller
from app.services.code_validator import CodeValidator
from app.services.codegen_planner_service import CodegenPlannerService
from app.services.codegen_service import CodegenService
from app.services.compile_validation_service import CompileValidationService
from app.services.enterprise_code_knowledge import get_enterprise_code_knowledge_service
from app.services.rag_service import get_rag_service
from app.services.resource_mapping_service import ResourceMappingService
from app.services.review_service import ReviewService
from app.services.run_store import get_run_store
from app.services.testplan_service import TestPlanService
from app.services.testprogram_service import TestProgramService

router = APIRouter()
run_store = get_run_store()
_review_service = ReviewService()
full_flow_controller = build_full_ate_development_controller(
    testplan_service=TestPlanService(),
    resource_mapping_service=ResourceMappingService(),
    planner=CodegenPlannerService(),
    codegen_service=CodegenService(),
    static_validator=CodeValidator(),
    compile_validator=CompileValidationService(),
    testprogram_service=TestProgramService(),
    knowledge=get_enterprise_code_knowledge_service(),
    rag_service=get_rag_service(),
    review_service=_review_service,
)
post_review_delivery_controller = build_post_review_delivery_controller()
post_review_revision_controller = build_post_review_revision_controller()


class AgentRunCreateRequest(BaseModel):
    flow_name: str = Field("module3_codegen", description="module3_codegen | full_ate_development")
    payload: Optional[CodegenRequest] = None
    goal: str = Field("", description="Natural-language engineering goal")
    file_id: Optional[str] = Field(None, description="Optional uploaded module1 file id")
    pdf_path: Optional[str] = Field(None, description="Optional direct PDF path")
    chip_name: str = Field("MyChip", description="Chip name for module 3 or fallback naming")
    chip_type: str = Field("digital", description="digital | ldo | custom")
    test_items: list[str] = Field(default_factory=list, description="Optional selected test items")
    user_prompt: str = Field("", description="Optional additional codegen prompt")
    auto_recommend: bool = Field(True, description="Auto recommend test items when empty")
    export_package: bool = Field(False, description="Export engineering package when possible")
    pages: Optional[str] = Field(None, description="Optional PDF page range for extraction")
    max_workers: int = Field(5, description="Extractor worker count")
    dual_site: bool = Field(False, description="Enable dual site resource mapping")
    vcc: float = Field(5.0, description="Supply voltage")
    vout: float = Field(3.3, description="LDO nominal output voltage")
    ldo_out_pin: int = Field(2, description="LDO output pin / channel")
    load_ma: float = Field(100.0, description="LDO load current in mA")
    async_mode: bool = Field(False, description="Run full_ate_development in background and return immediately")


def _build_full_flow_payload(req: AgentRunCreateRequest) -> dict:
    return {
        "goal": req.goal or req.user_prompt or "Generate a full STS8200S engineering package from Datasheet.",
        "file_id": req.file_id,
        "pdf_path": req.pdf_path,
        "chip_name": req.chip_name,
        "chip_type": req.chip_type,
        "test_items": req.test_items,
        "user_prompt": req.user_prompt,
        "auto_recommend": req.auto_recommend,
        "export_package": req.export_package,
        "pages": req.pages,
        "max_workers": req.max_workers,
        "dual_site": req.dual_site,
        "vcc": req.vcc,
        "vout": req.vout,
        "ldo_out_pin": req.ldo_out_pin,
        "load_ma": req.load_ma,
    }


def _run_full_flow_background(*, run_id: str, payload: dict, run_metadata: Optional[dict] = None) -> None:
    metadata = dict(run_metadata or {})
    try:
        run = full_flow_controller.run_flow(
            flow_name="full_ate_development",
            payload=payload,
            run_id=run_id,
            on_update=lambda snapshot: run_store.save_run({**snapshot.to_dict(), **metadata}),
        )
        run_store.save_run({**run.to_dict(), **metadata})
    except Exception as exc:  # pragma: no cover - defensive
        current = run_store.get_run(run_id) or {}
        current.update(
            {
                "run_id": run_id,
                "flow_name": "full_ate_development",
                "status": "failed",
                "updated_at": datetime.now().isoformat(),
                "errors": list(dict.fromkeys([*(current.get("errors") or []), str(exc)])),
                "warnings": current.get("warnings") or [],
                "steps": current.get("steps") or [],
                "artifacts": current.get("artifacts") or [],
                "shared": current.get("shared") or {},
                "input_payload": current.get("input_payload") or payload,
                "created_at": current.get("created_at") or datetime.now().isoformat(),
            }
        )
        current.update(metadata)
        run_store.save_run(current)


def _start_background_full_flow(
    *,
    payload: dict,
    run_id: Optional[str] = None,
    run_metadata: Optional[dict] = None,
    progress_message: str = "Run created and waiting for the first agent step.",
) -> dict:
    metadata = dict(run_metadata or {})
    resolved_run_id = run_id or f"full_ate_development_{uuid4().hex[:8]}"
    timestamp = datetime.now().isoformat()
    initial_run = {
        "run_id": resolved_run_id,
        "flow_name": "full_ate_development",
        "status": "running",
        "created_at": timestamp,
        "updated_at": timestamp,
        "input_payload": payload,
        "steps": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "shared": {
            "progress": {
                "phase": "queued",
                "message": progress_message,
                "planned_agents": full_flow_controller.get_flow_agent_names("full_ate_development"),
            }
        },
        **metadata,
    }
    run_store.save_run(initial_run)
    Thread(
        target=_run_full_flow_background,
        kwargs={"run_id": resolved_run_id, "payload": payload, "run_metadata": metadata},
        daemon=True,
    ).start()
    return initial_run


@router.post("", summary="Create an agent run")
async def create_agent_run(req: AgentRunCreateRequest = Body(...)):
    if req.flow_name == "module3_codegen":
        payload = req.payload or CodegenRequest(
            chip_name=req.chip_name,
            chip_type=req.chip_type,
            test_items=req.test_items,
            user_prompt=req.user_prompt,
            file_id=req.file_id,
            auto_recommend=req.auto_recommend,
            export_package=req.export_package,
            vcc=req.vcc,
            vout=req.vout,
            ldo_out_pin=req.ldo_out_pin,
            load_ma=req.load_ma,
        )
        http_code, outcome = run_codegen_flow(payload)
        if outcome["status"] == "success":
            return success(data=outcome["data"], message=outcome["message"], code=http_code)
        return error(outcome["message"], code=http_code, data=outcome["data"])

    if req.flow_name == "full_ate_development":
        payload = _build_full_flow_payload(req)
        if req.async_mode:
            initial_run = _start_background_full_flow(payload=payload)
            return success(
                data=initial_run,
                message="Full ATE development run started in background",
                code=202,
            )

        run = full_flow_controller.run_flow(
            flow_name="full_ate_development",
            payload=payload,
        )
        run_data = run.to_dict()
        run_store.save_run(run_data)
        if run.status == "failed":
            return error(run.errors[-1] if run.errors else "Full ATE development flow failed.", code=500, data=run_data)
        return success(
            data=run_data,
            message="Full ATE development run created",
            code=200,
        )

    return error("Unsupported flow_name. Supported: module3_codegen, full_ate_development", code=400)


@router.get("", summary="List persisted agent runs")
async def list_agent_runs(limit: int = 20, flow_name: Optional[str] = None):
    runs = run_store.list_runs(limit=limit, flow_name=flow_name)
    return paginate(runs, total=len(runs), page=1, page_size=limit, message="Agent runs loaded")


@router.delete("", summary="Clear persisted agent runs")
async def clear_agent_runs(flow_name: Optional[str] = None):
    deleted_count = run_store.clear_runs(flow_name=flow_name)
    return success(
        data={"deleted_count": deleted_count, "flow_name": flow_name},
        message="Agent runs cleared",
    )


@router.get("/{run_id}", summary="Get a single agent run")
async def get_agent_run(run_id: str):
    run = run_store.get_run(run_id)
    if not run:
        return error(f"Run not found: {run_id}", code=404)
    return success(data=run, message="Agent run loaded")


@router.get("/{run_id}/artifacts", summary="Get artifacts of an agent run")
async def get_agent_run_artifacts(run_id: str):
    run = run_store.get_run(run_id)
    if not run:
        return error(f"Run not found: {run_id}", code=404)
    return success(
        data={
            "run_id": run_id,
            "flow_name": run.get("flow_name"),
            "status": run.get("status"),
            "artifacts": run_store.get_artifacts(run_id),
        },
        message="Agent run artifacts loaded",
    )


@router.get("/{run_id}/artifacts/{artifact_name}", summary="Get a single artifact metadata record")
async def get_agent_run_artifact(run_id: str, artifact_name: str):
    run = run_store.get_run(run_id)
    if not run:
        return error(f"Run not found: {run_id}", code=404)
    artifact = run_store.get_artifact(run_id, artifact_name)
    if not artifact:
        return error(f"Artifact not found: {artifact_name}", code=404)
    return success(
        data={
            "run_id": run_id,
            "flow_name": run.get("flow_name"),
            "status": run.get("status"),
            "artifact": artifact,
        },
        message="Agent run artifact loaded",
    )


class ReviewDecisionRequest(BaseModel):
    reviewer: str = Field("ATE Engineer", description="Name or identifier of the reviewer")


class RejectDecisionRequest(BaseModel):
    reviewer: str = Field("ATE Engineer", description="Name or identifier of the reviewer")
    reason: str = Field("", description="Reason for rejection")
    rejection_type: str = Field(
        "engineering_decision",
        description="input_issue | engineering_decision | auto_fixable",
    )


def _normalize_rejection_type(rejection_type: str) -> str:
    normalized = (rejection_type or "").strip().lower()
    if normalized in {"input_issue", "engineering_decision", "auto_fixable"}:
        return normalized
    return "engineering_decision"


def _resolution_owner_for_rejection(rejection_type: str) -> str:
    if rejection_type == "auto_fixable":
        return "agent"
    return "user"


def _next_action_for_rejection(rejection_type: str) -> str:
    if rejection_type == "input_issue":
        return "Replace the source datasheet or provide the missing inputs before starting a new run."
    if rejection_type == "engineering_decision":
        return "Provide the missing engineering decision or bench constraint, then rerun the flow."
    return "Use the rejection evidence to create an agent-led revision run."


@router.post("/{run_id}/approve", summary="Approve a run awaiting human review")
async def approve_agent_run(run_id: str, req: ReviewDecisionRequest = Body(...)):
    run = run_store.get_run(run_id)
    if not run:
        return error(f"Run not found: {run_id}", code=404)
    if run.get("status") != "human_review_required":
        return error(f"Run is not awaiting human review (current status: {run.get('status')})", code=400)
    approved_run = run_store.approve_run(run_id, reviewer=req.reviewer)
    if not approved_run:
        return error(f"Run not found: {run_id}", code=404)
    continuation_run = post_review_delivery_controller.run_flow(
        flow_name="post_review_delivery",
        payload={
            "source_run": approved_run,
            "source_run_id": approved_run["run_id"],
            "review_source_run_id": approved_run["run_id"],
            "approved_by": req.reviewer or "ATE Engineer",
            "triggered_by": "approval",
            "file_id": approved_run.get("input_payload", {}).get("file_id"),
            "chip_name": approved_run.get("input_payload", {}).get("chip_name"),
            "chip_type": approved_run.get("input_payload", {}).get("chip_type"),
        },
        initial_shared={
            "source_run_summary": {
                "run_id": approved_run["run_id"],
                "flow_name": approved_run.get("flow_name"),
                "status": approved_run.get("status"),
            }
        },
    )
    continuation_run.parent_run_id = approved_run["run_id"]
    continuation_run.triggered_by = "approval"
    continuation_run.review_source_run_id = approved_run["run_id"]
    continuation_data = run_store.save_run(continuation_run.to_dict())
    approved_run = run_store.update_run_fields(
        run_id,
        continuation_run_id=continuation_data["run_id"],
        triggered_by="human_review_approval",
    ) or approved_run
    response_data = dict(approved_run)
    response_data["continuation_run"] = continuation_data
    return success(data=response_data, message="Run approved and continuation flow created")


@router.post("/{run_id}/reject", summary="Reject a run awaiting human review")
async def reject_agent_run(run_id: str, req: RejectDecisionRequest = Body(...)):
    run = run_store.get_run(run_id)
    if not run:
        return error(f"Run not found: {run_id}", code=404)
    if run.get("status") != "human_review_required":
        return error(f"Run is not awaiting human review (current status: {run.get('status')})", code=400)
    rejection_type = _normalize_rejection_type(req.rejection_type)
    resolution_owner = _resolution_owner_for_rejection(rejection_type)
    next_action = _next_action_for_rejection(rejection_type)
    updated = run_store.reject_run(
        run_id,
        reviewer=req.reviewer,
        reason=req.reason,
        rejection_type=rejection_type,
        resolution_owner=resolution_owner,
        next_action=next_action,
    )
    if not updated:
        return error(f"Run not found: {run_id}", code=404)
    continuation_run = post_review_revision_controller.run_flow(
        flow_name="post_review_revision",
        payload={
            "source_run": updated,
            "source_run_id": updated["run_id"],
            "review_source_run_id": updated["run_id"],
            "rejection_type": rejection_type,
            "reason": req.reason,
            "reviewer": req.reviewer or "ATE Engineer",
            "triggered_by": "rejection",
        },
    )
    continuation_run.parent_run_id = updated["run_id"]
    continuation_run.triggered_by = "rejection"
    continuation_run.review_source_run_id = updated["run_id"]
    continuation_data = run_store.save_run(continuation_run.to_dict())
    response_continuation = continuation_data
    update_fields = {
        "continuation_run_id": continuation_data["run_id"],
        "triggered_by": f"human_review_rejection:{rejection_type}",
    }

    if rejection_type == "auto_fixable":
        source_payload = dict(updated.get("input_payload") or {})
        revision_goal = source_payload.get("goal") or source_payload.get("user_prompt") or "Retry the full ATE development flow after review rejection."
        source_payload["goal"] = revision_goal
        source_payload["user_prompt"] = (
            f"{source_payload.get('user_prompt', '').strip()}\n\n"
            f"Revision objective: {req.reason.strip() or 'Apply the review feedback and regenerate the outputs.'}"
        ).strip()
        auto_revision_run = _start_background_full_flow(
            payload=source_payload,
            run_metadata={
                "parent_run_id": continuation_data["run_id"],
                "review_source_run_id": updated["run_id"],
                "triggered_by": "agent_revision:auto_fixable",
            },
            progress_message="Agent revision run created from review rejection and waiting for the first repair step.",
        )
        continuation_data = run_store.update_run_fields(
            continuation_data["run_id"],
            continuation_run_id=auto_revision_run["run_id"],
        ) or continuation_data
        response_continuation = auto_revision_run
        update_fields["continuation_run_id"] = auto_revision_run["run_id"]

    updated = run_store.update_run_fields(run_id, **update_fields) or updated
    response_data = dict(updated)
    response_data["continuation_run"] = response_continuation
    response_data["routing_run"] = continuation_data
    return success(data=response_data, message="Run rejected and revision flow created")

"""
Unified run-query endpoints for lightweight agent flows.
Phase 1 exposes persisted module 3 runs and their artifacts.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.api.v1.codegen import CodegenRequest, run_codegen_flow
from app.core.response import error, paginate, success
from app.services.run_store import get_run_store

router = APIRouter()
run_store = get_run_store()


class AgentRunCreateRequest(BaseModel):
    flow_name: str = Field("module3_codegen", description="Currently only module3_codegen is supported")
    payload: CodegenRequest


@router.post("", summary="Create an agent run")
async def create_agent_run(req: AgentRunCreateRequest = Body(...)):
    if req.flow_name != "module3_codegen":
        return error("Currently only module3_codegen is supported.", code=400)
    http_code, outcome = run_codegen_flow(req.payload)
    if outcome["status"] == "success":
        return success(data=outcome["data"], message=outcome["message"], code=http_code)
    return error(outcome["message"], code=http_code, data=outcome["data"])


@router.get("", summary="List persisted agent runs")
async def list_agent_runs(limit: int = 20, flow_name: Optional[str] = None):
    runs = run_store.list_runs(limit=limit, flow_name=flow_name)
    return paginate(runs, total=len(runs), page=1, page_size=limit, message="Agent runs loaded")


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

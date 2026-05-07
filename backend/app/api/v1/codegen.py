"""
Module 3 code generation API.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.response import error, success
from app.flows.module3_codegen_flow import (
    build_module3_codegen_controller,
    finalize_module3_run,
)
from app.services.code_validator import CodeValidator
from app.services.codegen_planner_service import CodegenPlannerService
from app.services.codegen_service import CodegenService, TEMPLATES
from app.services.compile_validation_service import CompileValidationService
from app.services.enterprise_code_knowledge import get_enterprise_code_knowledge_service
from app.services.review_service import ReviewService
from app.services.run_store import get_run_store
from app.services.testprogram_service import TestProgramService
from app.services.workspace_memory_service import get_workspace_memory_service
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()
router = APIRouter()

service = CodegenService()
validator = CodeValidator()
compile_validator = CompileValidationService()
planner = CodegenPlannerService()
testprogram_service = TestProgramService()
run_store = get_run_store()
workspace_memory = get_workspace_memory_service()
controller = build_module3_codegen_controller(
    planner=planner,
    service=service,
    static_validator=validator,
    compile_validator=compile_validator,
    testprogram_service=testprogram_service,
    review_service=ReviewService(),
)


class CodegenRequest(BaseModel):
    chip_name: str = Field("MyChip", description="Chip name")
    chip_type: str = Field("digital", description="digital | ldo | custom or extracted chip type")
    test_items: list[str] = Field(default_factory=list, description="Selected test items; empty means auto recommend")
    user_prompt: str = Field("", description="Natural language instruction")
    file_id: Optional[str] = Field(None, description="Optional extracted module 1 file id")
    auto_recommend: bool = Field(True, description="Auto fill test items when request leaves them empty")
    export_package: bool = Field(False, description="Export engineering package under processed/generated_programs")
    pin_names: Optional[list[str]] = Field(None, description="Pin names")
    input_pins: Optional[list[str]] = Field(None, description="Input pins")
    output_pins: Optional[list[str]] = Field(None, description="Output pins")
    vcc: float = Field(5.0, description="Supply voltage")
    vout: float = Field(3.3, description="LDO nominal output voltage")
    ldo_out_pin: int = Field(2, description="LDO output pin / channel")
    load_ma: float = Field(100.0, description="LDO load current in mA")


class RecommendRequest(BaseModel):
    chip_type: Optional[str] = Field(None, description="Chip type")
    file_id: Optional[str] = Field(None, description="Module 1 extracted file id")


def _load_testplan_by_file_id(file_id: str) -> Optional[dict]:
    candidates = sorted(settings.PROCESSED_DIR.glob(f"*{file_id}*TestPlan.json"))
    if not candidates:
        return None
    return json.loads(Path(candidates[-1]).read_text(encoding="utf-8"))


def _available_items() -> set[str]:
    knowledge = get_enterprise_code_knowledge_service()
    return set(knowledge.get_catalog()["available_items"].keys()) | set(TEMPLATES.keys())


def _recommend_payload(chip_type: Optional[str], file_id: Optional[str]) -> dict:
    knowledge = get_enterprise_code_knowledge_service()
    resolved_chip_type = chip_type or "custom"
    param_names: list[str] = []
    source = "manual"

    if file_id:
        data = _load_testplan_by_file_id(file_id)
        if data:
            resolved_chip_type = data.get("chip_type") or resolved_chip_type
            param_names = [param.get("param_name", "") for param in data.get("parameters", [])]
            source = "module1"

    recommended_items = knowledge.recommend_test_items(resolved_chip_type, param_names=param_names)
    scenario = knowledge.resolve_scenario(resolved_chip_type)
    scenario_items = knowledge.get_catalog()["scenario_items"].get(scenario, [])
    optional_items = [item for item in scenario_items if item not in recommended_items]
    detected_params = sorted({name for name in (str(item or "").upper() for item in param_names) if name})
    reason_summary: list[str] = []
    if source == "module1" and detected_params:
        preview = ", ".join(detected_params[:8])
        suffix = " ..." if len(detected_params) > 8 else ""
        reason_summary.append(f"模块一提取参数命中: {preview}{suffix}")
    if scenario:
        reason_summary.append(f"当前场景判定为 {scenario}，按企业样本知识库排序推荐测试项。")
    if recommended_items:
        reason_summary.append(f"优先推荐 {len(recommended_items)} 项，覆盖当前芯片常见 DC/AC/功能测试骨架。")
    return {
        "chip_type": resolved_chip_type,
        "scenario": scenario,
        "source": source,
        "recommended_items": recommended_items,
        "optional_items": optional_items,
        "detected_params": detected_params,
        "reason_summary": reason_summary,
        "available_items": [item["id"] for item in knowledge.list_items(resolved_chip_type)],
    }


def run_codegen_flow(req: CodegenRequest) -> tuple[int, dict]:
    knowledge = get_enterprise_code_knowledge_service()
    recommendation = _recommend_payload(req.chip_type, req.file_id)

    test_items = list(req.test_items)
    if not test_items and req.auto_recommend:
        test_items = recommendation["recommended_items"]

    unknown = [item for item in test_items if item not in _available_items()]
    if unknown:
        return 400, {
            "status": "error",
            "message": f"Unknown test items: {unknown}. Supported items: {sorted(_available_items())}",
            "data": None,
        }
    if not test_items:
        return 400, {
            "status": "error",
            "message": "Please select at least one test item or enable auto recommendation.",
            "data": None,
        }

    payload = {
        "chip_name": req.chip_name,
        "chip_type": req.chip_type,
        "test_items": test_items,
        "user_prompt": req.user_prompt,
        "file_id": req.file_id,
        "export_package": req.export_package,
        "pin_names": req.pin_names,
        "input_pins": req.input_pins,
        "output_pins": req.output_pins,
        "vcc": req.vcc,
        "vout": req.vout,
        "ldo_out_pin": req.ldo_out_pin,
        "load_ma": req.load_ma,
    }

    run = controller.run_flow(
        flow_name="module3_codegen",
        payload=payload,
        initial_shared={
            "recommendation": recommendation,
            "selected_test_items": test_items,
        },
    )
    run_store.save_run(run.to_dict())

    if run.status not in {"completed", "human_review_required", "warning"}:
        last_step = run.steps[-1] if run.steps else {}
        http_code = int(last_step.get("metadata", {}).get("http_code", 500))
        failure_kind = last_step.get("metadata", {}).get("failure_kind")
        if failure_kind == "blocking_constraints":
            return http_code, {
                "status": "error",
                "message": "Generation plan contains blocking business constraints. Please fix the highlighted issues before generating code.",
                "data": run.shared.get("plan"),
            }
        return http_code, {
            "status": "error",
            "message": run.errors[-1] if run.errors else "Code generation failed.",
            "data": {"run": run.to_dict(), "plan": run.shared.get("plan")},
        }

    result = finalize_module3_run(run, knowledge)
    run_store.save_run(run.to_dict())
    return 200, {
        "status": "success",
        "message": "Code generated successfully",
        "data": result,
    }


@router.post("/generate", summary="Generate STS8200S test code")
async def generate_code(req: CodegenRequest = Body(...)):
    try:
        http_code, outcome = run_codegen_flow(req)
        if outcome["status"] == "success":
            result = outcome["data"] or {}
            workspace_memory.update_codegen_context(
                {
                    "template": ", ".join(result.get("test_items", [])[:4]) or req.chip_type,
                    "summary": (
                        f"{result.get('chip_name', req.chip_name)} / {result.get('chip_type', req.chip_type)} / "
                        f"测试项 {len(result.get('test_items', []))} 个 / 代码 {result.get('lines', 0)} 行"
                    ),
                }
            )
            return success(data=outcome["data"], message=outcome["message"], code=http_code)
        return error(outcome["message"], code=http_code, data=outcome["data"])
    except Exception as exc:  # pragma: no cover - defensive route fallback
        logger.error(f"Code generation failed: {exc}")
        import traceback

        logger.error(traceback.format_exc())
        return error(f"Code generation failed: {exc}", code=500)


@router.post("/recommend", summary="Recommend test items from module 1 result or chip type")
async def recommend_code_items(req: RecommendRequest = Body(...)):
    return success(data=_recommend_payload(req.chip_type, req.file_id), message="Recommendation ready")


@router.post("/plan", summary="Build structured generation plan before code assembly")
async def build_codegen_plan(req: CodegenRequest = Body(...)):
    recommendation = _recommend_payload(req.chip_type, req.file_id)
    test_items = list(req.test_items)
    if not test_items and req.auto_recommend:
        test_items = recommendation["recommended_items"]
    plan = planner.build_plan(
        chip_name=req.chip_name,
        chip_type=recommendation["chip_type"],
        test_items=test_items,
        pin_names=req.pin_names,
        input_pins=req.input_pins,
        output_pins=req.output_pins,
        vcc=req.vcc,
        vout=req.vout,
        ldo_out_pin=req.ldo_out_pin,
        load_ma=req.load_ma,
    )
    return success(data=plan, message="Code generation plan ready")


@router.get("/templates", summary="List supported test items")
async def list_templates():
    knowledge = get_enterprise_code_knowledge_service()
    digital = knowledge.list_items("digital")
    analog = knowledge.list_items("ldo")
    extra = [
        {"id": key, "name": key, "desc": "Built-in fallback template", "apis": [], "scenarios": ["fallback"]}
        for key in sorted(set(TEMPLATES.keys()) - {item["id"] for item in digital} - {item["id"] for item in analog})
    ]
    return success(
        data={
            "digital": digital,
            "ldo": analog + extra,
            "knowledge_summary": knowledge.summary(),
        },
        message="Supported test items loaded",
    )


@router.get("/knowledge", summary="Inspect enterprise code knowledge base")
async def knowledge_status():
    knowledge = get_enterprise_code_knowledge_service()
    return success(data=knowledge.summary(), message="Enterprise code knowledge loaded")

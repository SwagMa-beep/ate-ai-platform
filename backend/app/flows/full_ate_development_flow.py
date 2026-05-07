"""Cross-module ATE development flow built on top of AgentController."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.core.config import get_settings
from app.models.resource_map import (
    AdapterInfo,
    PGSConfig,
    PGSDetailCondition,
    PinGroupConfig,
    ResourceMapping,
)
from app.models.testplan import ExtractionResult
from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent, RunContext
from app.services.code_validator import CodeValidator
from app.services.codegen_planner_service import CodegenPlannerService
from app.services.codegen_service import CodegenService
from app.services.compile_validation_service import CompileValidationService
from app.services.enterprise_code_knowledge import EnterpriseCodeKnowledgeService
from app.services.rag_service import RAGService
from app.services.resource_mapping_service import ResourceMappingService
from app.services.review_service import ReviewService
from app.services.testplan_service import TestPlanService
from app.services.testprogram_service import TestProgramService
from app.utils.bom_generator import generate_bom_excel
from app.utils.logger import setup_logger
from app.utils.resource_map_exporter import export_resource_map_excel
from app.utils.svg_generator import SVGGenerator

settings = get_settings()
logger = setup_logger()


def _find_uploaded_pdf(file_id: Optional[str]) -> Optional[Path]:
    if not file_id:
        return None
    matches = sorted(settings.UPLOAD_DIR.glob(f"{file_id}_*"))
    return matches[-1] if matches else None


def _build_extraction_model(result_data: Dict[str, Any]) -> ExtractionResult:
    return ExtractionResult(
        status="success",
        chip_name=result_data.get("chip_name", "Unknown"),
        chip_type=result_data.get("chip_type", "UNKNOWN"),
        test_scenario=result_data.get("test_scenario", "GENERAL"),
        total_params=result_data.get("total_params", 0),
        a_params=result_data.get("a_params", 0),
        b_params=result_data.get("b_params", 0),
        c_params=result_data.get("c_params", 0),
        blocked_params=result_data.get("blocked_params", 0),
        dc_test_items=result_data.get("dc_test_items", 0),
        ac_test_items=result_data.get("ac_test_items", 0),
        ldo_test_items=result_data.get("ldo_test_items", 0),
    )


def _split_pin_groups(pin_definitions: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    pin_names: List[str] = []
    input_pins: List[str] = []
    output_pins: List[str] = []
    power_like: List[str] = []
    for pin in pin_definitions:
        pin_name = str(pin.get("pin_name") or "").strip()
        if not pin_name:
            continue
        direction = str(pin.get("direction") or "IN").upper()
        pin_names.append(pin_name)
        if direction == "OUT":
            output_pins.append(pin_name)
        elif direction in {"PWR", "GND"}:
            power_like.append(pin_name)
        else:
            input_pins.append(pin_name)
    return {
        "pin_names": pin_names,
        "input_pins": input_pins,
        "output_pins": output_pins,
        "power_like": power_like,
    }


def _recommend_codegen_items(
    knowledge: EnterpriseCodeKnowledgeService,
    *,
    chip_type: str,
    extraction_result: Dict[str, Any],
) -> Dict[str, Any]:
    param_names = [param.get("param_name", "") for param in extraction_result.get("parameters", [])]
    recommended_items = knowledge.recommend_test_items(chip_type, param_names=param_names)
    scenario = knowledge.resolve_scenario(chip_type)
    return {
        "chip_type": chip_type,
        "scenario": scenario,
        "recommended_items": recommended_items,
        "detected_params": sorted({name for name in (str(item or "").upper() for item in param_names) if name}),
        "source": "full_flow",
    }


class FullInputResolveAgent(BaseAgent):
    agent_name = "input_resolver"

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        resolved_pdf = payload.get("pdf_path")
        if not resolved_pdf and payload.get("file_id"):
            match = _find_uploaded_pdf(payload.get("file_id"))
            resolved_pdf = str(match) if match else None

        if not payload.get("goal"):
            return AgentStepResult(
                agent=self.agent_name,
                status="failed",
                message="A full ATE run requires a goal.",
                errors=["goal is required for full_ate_development"],
            )
        if not resolved_pdf or not Path(resolved_pdf).exists():
            return AgentStepResult(
                agent=self.agent_name,
                status="failed",
                message="No Datasheet PDF could be resolved.",
                errors=["pdf_path or file_id is required, and the target PDF must exist."],
            )

        resolved = {
            "goal": payload.get("goal"),
            "file_id": payload.get("file_id"),
            "pdf_path": resolved_pdf,
            "target_platform": "STS8200S",
        }
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Input resolved for full ATE flow.",
            output={"resolved_input": resolved},
            artifacts=[
                {
                    "type": "source_pdf",
                    "summary": {
                        "file_id": payload.get("file_id"),
                        "pdf_path": resolved_pdf,
                        "target_platform": "STS8200S",
                    },
                }
            ],
        )


class FullTestPlanExtractAgent(BaseAgent):
    agent_name = "testplan_extractor"

    def __init__(self, service: TestPlanService) -> None:
        self.service = service

    def run(self, context: RunContext) -> AgentStepResult:
        resolved_input = context.shared["resolved_input"]
        result = self.service.extract_from_pdf(
            pdf_path=resolved_input["pdf_path"],
            pages=context.input_payload.get("pages"),
            max_workers=context.input_payload.get("max_workers", 5),
        )
        result_data = result.model_dump()
        status = "completed" if result.status == "success" else "failed"
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            message="TestPlan extraction finished." if status == "completed" else "TestPlan extraction failed.",
            output={"extraction_result": result_data},
            warnings=list(result.warnings or []),
            errors=list(result.errors or []),
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
            metadata={"http_code": 200 if status == "completed" else 500},
        )


class FullParamValidationAgent(BaseAgent):
    agent_name = "param_validator"

    def run(self, context: RunContext) -> AgentStepResult:
        result_data = context.shared["extraction_result"]
        pin_definitions = list(result_data.get("pin_definitions") or [])
        warnings: List[str] = []
        must_review_items: List[str] = []
        passed = True

        if not pin_definitions:
            passed = False
            must_review_items.append("未提取到有效引脚定义，无法继续执行后续资源映射与代码生成。")
        if not result_data.get("parameters"):
            warnings.append("未提取到稳定参数表，后续生成结果需要重点人工复核。")
        if not any(str(pin.get("direction", "")).upper() == "PWR" for pin in pin_definitions):
            warnings.append("未识别到电源引脚，请人工确认供电定义是否完整。")
        if not any(str(pin.get("direction", "")).upper() == "GND" for pin in pin_definitions):
            warnings.append("未识别到地引脚，请人工确认接地定义是否完整。")

        validation = {
            "passed": passed,
            "missing_fields": must_review_items,
            "warnings": warnings,
        }
        status = "completed" if passed else "human_review_required"
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            message="Parameter validation finished." if passed else "Extraction needs engineer review before continuing.",
            output={"validation": validation},
            warnings=warnings + must_review_items,
            errors=[],
            artifacts=[
                {
                    "type": "validation_summary",
                    "summary": {
                        "passed": passed,
                        "pin_count": len(pin_definitions),
                        "warning_count": len(warnings),
                    },
                }
            ],
            requires_human_review=not passed,
            next_action="Review extracted pin definitions and required power pins." if not passed else None,
        )


class FullResourceMappingAgent(BaseAgent):
    agent_name = "resource_mapper"

    def __init__(self, service: ResourceMappingService, svg_generator: SVGGenerator) -> None:
        self.service = service
        self.svg_generator = svg_generator

    def should_run(self, context: RunContext) -> bool:
        return bool(context.shared.get("validation", {}).get("passed"))

    def run(self, context: RunContext) -> AgentStepResult:
        extraction_result = context.shared["extraction_result"]
        extraction_model = _build_extraction_model(extraction_result)
        pin_df = pd.DataFrame(extraction_result.get("pin_definitions") or [])
        result = self.service.generate_resource_map(
            extraction_model,
            pin_df,
            context.input_payload.get("dual_site", False),
        )
        result_data = result.model_dump()
        status = "completed" if result.status == "success" else "failed"
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            message="Resource mapping finished." if status == "completed" else "Resource mapping failed.",
            output={"resource_map_result": result_data},
            warnings=list(result.warnings or []),
            errors=list(result.errors or []),
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
        )


class FullRagRetrievalAgent(BaseAgent):
    agent_name = "rag_retriever"

    def __init__(self, rag_service: RAGService, knowledge: EnterpriseCodeKnowledgeService) -> None:
        self.rag_service = rag_service
        self.knowledge = knowledge

    def should_run(self, context: RunContext) -> bool:
        return bool(context.input_payload.get("goal") or context.input_payload.get("user_prompt"))

    def max_retries(self) -> int:
        return 1

    def run(self, context: RunContext) -> AgentStepResult:
        query = context.input_payload.get("user_prompt") or context.input_payload.get("goal") or ""
        extraction_result = context.shared.get("extraction_result") or {}
        chip_name = extraction_result.get("chip_name") or context.input_payload.get("chip_name")
        chip_type = extraction_result.get("chip_type") or context.input_payload.get("chip_type")
        recommended = _recommend_codegen_items(
            self.knowledge,
            chip_type=chip_type or "custom",
            extraction_result=extraction_result,
        )
        selected_items = list(context.input_payload.get("test_items") or recommended["recommended_items"])
        if not self.rag_service.is_ready:
            return AgentStepResult(
                agent=self.agent_name,
                status="warning",
                message="RAG is not ready, falling back to enterprise knowledge only.",
                warnings=["RAG 当前不可用，后续代码生成将退回企业知识库与模板模式。"],
                output={"rag": {"query": query, "chunks": [], "hit_count": 0, "ready": False}},
                artifacts=[{"type": "rag_context", "summary": {"hit_count": 0, "ready": False, "fallback_used": True}}],
                next_action="Review the generated plan with extra attention to platform API usage because no RAG context was available.",
            )

        chunks = self.rag_service.retrieve(
            query,
            top_k=5,
            chip_name=chip_name,
            chip_type=chip_type,
            test_items=selected_items,
        )
        warnings: List[str] = []
        status = "completed"
        if not chunks:
            status = "warning"
            warnings.append("RAG 未返回有效片段，后续代码生成将继续使用企业知识库与模板兜底。")
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            message="RAG retrieval finished." if chunks else "RAG retrieval returned no useful chunk.",
            warnings=warnings,
            output={"rag": {"query": query, "chunks": chunks, "hit_count": len(chunks), "ready": True}},
            artifacts=[{"type": "rag_context", "summary": {"hit_count": len(chunks), "ready": True, "fallback_used": not bool(chunks), "test_items": selected_items[:6]}}],
            next_action="Review enterprise knowledge matches because no stable RAG chunk was found." if not chunks else None,
        )


class FullCodegenPlanningAgent(BaseAgent):
    agent_name = "codegen_planner"

    def __init__(self, planner: CodegenPlannerService, knowledge: EnterpriseCodeKnowledgeService) -> None:
        self.planner = planner
        self.knowledge = knowledge

    def should_run(self, context: RunContext) -> bool:
        return bool(context.shared.get("validation", {}).get("passed"))

    def run(self, context: RunContext) -> AgentStepResult:
        extraction_result = context.shared["extraction_result"]
        chip_type = extraction_result.get("chip_type") or context.input_payload.get("chip_type") or "custom"
        recommendation = _recommend_codegen_items(self.knowledge, chip_type=chip_type, extraction_result=extraction_result)
        pin_groups = _split_pin_groups(extraction_result.get("pin_definitions") or [])
        selected_items = list(context.input_payload.get("test_items") or recommendation["recommended_items"])
        plan = self.planner.build_plan(
            chip_name=extraction_result.get("chip_name", "UnknownChip"),
            chip_type=recommendation["chip_type"],
            test_items=selected_items,
            pin_names=pin_groups["pin_names"],
            input_pins=pin_groups["input_pins"],
            output_pins=pin_groups["output_pins"],
            vcc=context.input_payload.get("vcc", 5.0),
            vout=context.input_payload.get("vout", 3.3),
            ldo_out_pin=context.input_payload.get("ldo_out_pin", 2),
            load_ma=context.input_payload.get("load_ma", 100.0),
        )
        status = "failed" if plan["errors"] else "completed"
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            message="Code generation plan finished." if not plan["errors"] else "Code generation plan hit blocking constraints.",
            output={
                "recommendation": recommendation,
                "selected_test_items": selected_items,
                "pin_groups": pin_groups,
                "plan": plan,
            },
            warnings=plan["warnings"],
            errors=plan["errors"],
            artifacts=[
                {
                    "type": "codegen_plan",
                    "summary": {
                        "selected_items": selected_items,
                        "requires_vector": plan["requires_vector"],
                        "requires_pgs": plan["requires_pgs"],
                    },
                }
            ],
        )


class FullCodeAssemblyAgent(BaseAgent):
    agent_name = "code_assembler"

    def __init__(self, service: CodegenService) -> None:
        self.service = service

    def should_run(self, context: RunContext) -> bool:
        plan = context.shared.get("plan") or {}
        return not bool(plan.get("errors"))

    def run(self, context: RunContext) -> AgentStepResult:
        extraction_result = context.shared["extraction_result"]
        recommendation = context.shared["recommendation"]
        pin_groups = context.shared["pin_groups"]
        selected_items = context.shared["selected_test_items"]
        user_prompt = context.input_payload.get("user_prompt") or context.input_payload.get("goal") or ""
        result = self.service.generate(
            chip_name=extraction_result.get("chip_name", "UnknownChip"),
            chip_type=recommendation["chip_type"],
            test_items=selected_items,
            user_prompt=user_prompt,
            pin_names=pin_groups["pin_names"],
            input_pins=pin_groups["input_pins"],
            output_pins=pin_groups["output_pins"],
            vcc=context.input_payload.get("vcc", 5.0),
            vout=context.input_payload.get("vout", 3.3),
            ldo_out_pin=context.input_payload.get("ldo_out_pin", 2),
            load_ma=context.input_payload.get("load_ma", 100.0),
        )
        result["plan"] = context.shared.get("plan")
        result["recommendation"] = recommendation
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Code assembly finished.",
            output={"generated_result": result},
            artifacts=[{"type": "generated_code", "summary": {"filename": result.get("filename"), "functions": result.get("functions")}}],
        )


class FullStaticValidationAgent(BaseAgent):
    agent_name = "static_validator"

    def __init__(self, validator: CodeValidator) -> None:
        self.validator = validator

    def should_run(self, context: RunContext) -> bool:
        return bool(context.shared.get("generated_result"))

    def run(self, context: RunContext) -> AgentStepResult:
        result = context.shared["generated_result"]
        try:
            static_analysis = self.validator.validate(result.get("code", "")).to_dict()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Static validation failed in full flow: {exc}")
            static_analysis = {}
        result["static_analysis"] = static_analysis
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Static validation finished.",
            output={"generated_result": result},
            artifacts=[{"type": "static_analysis", "summary": {"passed": static_analysis.get("passed")}}],
        )


class FullCompileValidationAgent(BaseAgent):
    agent_name = "compile_validator"

    def __init__(self, validator: CompileValidationService) -> None:
        self.validator = validator

    def should_run(self, context: RunContext) -> bool:
        return bool(context.shared.get("generated_result"))

    def run(self, context: RunContext) -> AgentStepResult:
        result = context.shared["generated_result"]
        try:
            compile_analysis = self.validator.validate(
                result.get("code", ""),
                filename=result.get("filename", "generated_test.cpp"),
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Compile validation failed in full flow: {exc}")
            compile_analysis = {"passed": False, "issues": [str(exc)], "mode": "simulated_compile_check"}
        result["compile_validation"] = compile_analysis
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Compile precheck finished.",
            warnings=[
                "当前环境未配置真实 STS8200S 编译链时，仅执行结构化编译预检。"
            ] if compile_analysis.get("mode") == "simulated_compile_check" else [],
            output={"generated_result": result},
            artifacts=[{"type": "compile_validation", "summary": {"passed": compile_analysis.get("passed"), "mode": compile_analysis.get("mode")}}],
            next_action="Re-run in a workstation with the real STS compile toolchain if you need closer-to-bench verification."
            if compile_analysis.get("mode") == "simulated_compile_check"
            else None,
        )


class FullReviewAgent(BaseAgent):
    agent_name = "review_agent"

    def __init__(self, review_service: Optional[ReviewService] = None) -> None:
        self.review_service = review_service

    def should_run(self, context: RunContext) -> bool:
        return bool(context.shared.get("generated_result"))

    def run(self, context: RunContext) -> AgentStepResult:
        if self.review_service:
            review = self.review_service.generate_review(
                context.shared, steps=context.steps,
            )
        else:
            review = self._deterministic_review(context.shared)

        result = dict(context.shared.get("generated_result") or {})
        result["review"] = review
        must_review_items = list(review.get("must_review_items") or [])
        return AgentStepResult(
            agent=self.agent_name,
            status="warning",
            message="Full ATE flow finished and requires engineer review.",
            output={"generated_result": result, "review": review},
            warnings=must_review_items,
            artifacts=[
                {
                    "type": "review_summary",
                    "summary": {
                        "overall_status": review["overall_status"],
                        "risk_level": review["risk_level"],
                        "must_review_count": len(must_review_items),
                        "fallback_used": review.get("confidence_score", 1.0) == 0.0,
                        "confidence_score": review.get("confidence_score", 0.0),
                    },
                }
            ],
            requires_human_review=True,
            next_action="Review the generated artifacts and validation output before bench integration.",
        )

    @staticmethod
    def _deterministic_review(shared: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(shared.get("generated_result") or {})
        validation = shared.get("validation") or {}
        rag = shared.get("rag") or {}
        plan = result.get("plan") or shared.get("plan") or {}
        static_analysis = result.get("static_analysis") or {}
        compile_validation = result.get("compile_validation") or {}

        must_review_items = ["生成结果仅用于辅助测试开发，需由 ATE 工程师复核后再上机使用。"]
        recommendations: List[str] = []
        risk_level = "medium"

        if not validation.get("passed", False):
            must_review_items.append("参数校验未完全通过，请先确认提取结果是否足够支持后续工程。")
            risk_level = "high"
        if not rag.get("hit_count"):
            recommendations.append("RAG 未提供稳定上下文，建议优先对平台 API 使用进行人工复核。")
        if static_analysis and not static_analysis.get("passed", True):
            must_review_items.append("静态校验存在未修复项。")
            risk_level = "high"
        if compile_validation and not compile_validation.get("passed", True):
            must_review_items.append("编译预检未通过。")
            recommendations.append("先修正编译预检报错，再决定是否导出正式工程包。")
            risk_level = "high"
        if plan.get("requires_vector"):
            must_review_items.append("请复核 VECDIO 相关向量文件、label 和 time set。")
        if plan.get("requires_pgs"):
            must_review_items.append("请复核 PGS、AutoLoad 与资源映射配置。")

        return {
            "overall_status": "needs_human_review",
            "summary": "全链路结果已生成，但仍需人工复核测试逻辑、平台调用和工程配置。",
            "risk_level": risk_level,
            "must_review_items": must_review_items,
            "recommendations": recommendations or ["建议结合运行中心与工程包，逐项完成测试工程复核。"],
            "confidence_score": 0.0,
        }


class FullEngineeringPackageAgent(BaseAgent):
    agent_name = "engineering_packager"

    def __init__(self, testprogram_service: TestProgramService) -> None:
        self.testprogram_service = testprogram_service

    def should_run(self, context: RunContext) -> bool:
        return bool(context.input_payload.get("export_package") and context.shared.get("generated_result"))

    def run(self, context: RunContext) -> AgentStepResult:
        file_id = context.input_payload.get("file_id")
        result = context.shared["generated_result"]
        if not file_id:
            return AgentStepResult(
                agent=self.agent_name,
                status="warning",
                message="Engineering package export skipped because file_id is missing.",
                warnings=["未提供 file_id，本次无法自动导出与模块一产物关联的工程包。"],
                next_action="Provide file_id from module 1 upload if you need a linked engineering package.",
            )

        package = self.testprogram_service.export_package(
            file_id=file_id,
            chip_name=result["chip_name"],
            chip_type=result["chip_type"],
            test_items=result["test_items"],
            code=result["code"],
            user_prompt=context.input_payload.get("user_prompt") or context.input_payload.get("goal") or "",
            source="full_ate_development",
            generator_mode="full_ate_development",
            extra_notes=[
                "Package exported from the full_ate_development flow.",
                "Review resource mapping, vector labels, compile diagnostics and review summary before bench usage.",
            ],
        )
        result["package_export"] = package.model_dump()
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Engineering package exported.",
            output={"generated_result": result},
            artifacts=[{"type": "engineering_package", "summary": {"generation_id": package.generation_id}}],
        )


def build_full_ate_development_controller(
    *,
    testplan_service: TestPlanService,
    resource_mapping_service: ResourceMappingService,
    planner: CodegenPlannerService,
    codegen_service: CodegenService,
    static_validator: CodeValidator,
    compile_validator: CompileValidationService,
    testprogram_service: TestProgramService,
    knowledge: EnterpriseCodeKnowledgeService,
    rag_service: RAGService,
    review_service: Optional[ReviewService] = None,
) -> AgentController:
    controller = AgentController()
    controller.register_flow(
        "full_ate_development",
        [
            FullInputResolveAgent(),
            FullTestPlanExtractAgent(testplan_service),
            FullParamValidationAgent(),
            FullResourceMappingAgent(resource_mapping_service, SVGGenerator()),
            FullRagRetrievalAgent(rag_service, knowledge),
            FullCodegenPlanningAgent(planner, knowledge),
            FullCodeAssemblyAgent(codegen_service),
            FullStaticValidationAgent(static_validator),
            FullCompileValidationAgent(compile_validator),
            FullReviewAgent(review_service=review_service),
            FullEngineeringPackageAgent(testprogram_service),
        ],
    )
    return controller

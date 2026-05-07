"""
Module 3 code-generation flow built on top of the lightweight AgentController.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent, RunContext
from app.services.code_validator import CodeValidator
from app.services.codegen_planner_service import CodegenPlannerService
from app.services.codegen_service import CodegenService
from app.services.compile_validation_service import CompileValidationService
from app.services.enterprise_code_knowledge import EnterpriseCodeKnowledgeService
from app.services.review_service import ReviewService
from app.services.testprogram_service import TestProgramService
from app.utils.logger import setup_logger

logger = setup_logger()


class Module3PlanningAgent(BaseAgent):
    agent_name = "codegen_planner"

    def __init__(self, planner: CodegenPlannerService) -> None:
        self.planner = planner

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        recommendation = context.shared["recommendation"]
        test_items = context.shared["selected_test_items"]
        plan = self.planner.build_plan(
            chip_name=payload["chip_name"],
            chip_type=recommendation["chip_type"],
            test_items=test_items,
            pin_names=payload.get("pin_names"),
            input_pins=payload.get("input_pins"),
            output_pins=payload.get("output_pins"),
            vcc=payload.get("vcc", 5.0),
            vout=payload.get("vout", 3.3),
            ldo_out_pin=payload.get("ldo_out_pin", 2),
            load_ma=payload.get("load_ma", 100.0),
        )
        status = "failed" if plan["errors"] else "completed"
        return AgentStepResult(
            agent=self.agent_name,
            status=status,
            output={"plan": plan},
            warnings=plan["warnings"],
            errors=plan["errors"],
            artifacts=[
                {
                    "type": "codegen_plan",
                    "summary": {
                        "selected_items": plan["selected_items"],
                        "requires_vector": plan["requires_vector"],
                        "requires_pgs": plan["requires_pgs"],
                    },
                }
            ],
            metadata={
                "http_code": 400 if plan["errors"] else 200,
                "failure_kind": "blocking_constraints" if plan["errors"] else None,
            },
        )


class Module3AssemblyAgent(BaseAgent):
    agent_name = "code_assembler"

    def __init__(self, service: CodegenService) -> None:
        self.service = service

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        recommendation = context.shared["recommendation"]
        test_items = context.shared["selected_test_items"]
        result = self.service.generate(
            chip_name=payload["chip_name"],
            chip_type=recommendation["chip_type"],
            test_items=test_items,
            user_prompt=payload.get("user_prompt", ""),
            pin_names=payload.get("pin_names"),
            input_pins=payload.get("input_pins"),
            output_pins=payload.get("output_pins"),
            vcc=payload.get("vcc", 5.0),
            vout=payload.get("vout", 3.3),
            ldo_out_pin=payload.get("ldo_out_pin", 2),
            load_ma=payload.get("load_ma", 100.0),
        )
        result["plan"] = context.shared.get("plan")
        result["recommendation"] = recommendation
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            output={"generated_result": result},
            artifacts=[
                {
                    "type": "generated_code",
                    "summary": {
                        "filename": result.get("filename"),
                        "functions": result.get("functions"),
                    },
                }
            ],
        )


class Module3StaticValidationAgent(BaseAgent):
    agent_name = "static_validator"

    def __init__(self, validator: CodeValidator) -> None:
        self.validator = validator

    def run(self, context: RunContext) -> AgentStepResult:
        result = context.shared["generated_result"]
        try:
            static_analysis = self.validator.validate(result.get("code", "")).to_dict()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Static validation skipped due to error: {exc}")
            static_analysis = {}
        result["static_analysis"] = static_analysis
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Static code checks finished.",
            output={"generated_result": result},
            artifacts=[{"type": "static_analysis", "summary": {"passed": static_analysis.get("passed")}}],
        )


class Module3CompileValidationAgent(BaseAgent):
    agent_name = "compile_validator"

    def __init__(self, validator: CompileValidationService) -> None:
        self.validator = validator

    def run(self, context: RunContext) -> AgentStepResult:
        result = context.shared["generated_result"]
        try:
            compile_analysis = self.validator.validate(
                result.get("code", ""),
                filename=result.get("filename", "generated_test.cpp"),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Compile validation skipped due to error: {exc}")
            compile_analysis = {}
        result["compile_validation"] = compile_analysis
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Compile precheck finished.",
            output={"generated_result": result},
            artifacts=[{"type": "compile_validation", "summary": {"passed": compile_analysis.get("passed")}}],
        )


class Module3ReviewAgent(BaseAgent):
    agent_name = "review_agent"

    def __init__(self, review_service: Optional[ReviewService] = None) -> None:
        self.review_service = review_service

    def should_run(self, context: RunContext) -> bool:
        return bool(context.shared.get("generated_result"))

    def run(self, context: RunContext) -> AgentStepResult:
        result = dict(context.shared.get("generated_result") or {})
        plan = result.get("plan") or context.shared.get("plan") or {}
        static_analysis = result.get("static_analysis") or {}
        compile_validation = result.get("compile_validation") or {}
        package_export = result.get("package_export") or {}

        if self.review_service:
            review = self.review_service.generate_review(
                context.shared, steps=context.steps,
            )
        else:
            review = self._deterministic_review(
                plan, static_analysis, compile_validation, package_export,
            )

        result["review"] = review
        must_review_items = list(review.get("must_review_items") or [])
        return AgentStepResult(
            agent=self.agent_name,
            status="warning",
            message="Generated code requires engineer review before bench usage.",
            output={"generated_result": result, "review": review},
            warnings=must_review_items,
            artifacts=[
                {
                    "type": "review_summary",
                    "summary": {
                        "overall_status": review["overall_status"],
                        "risk_level": review["risk_level"],
                        "must_review_count": len(must_review_items),
                        "confidence_score": review.get("confidence_score", 0.0),
                    },
                }
            ],
            requires_human_review=True,
            next_action="Review the generated package and validation results before bench integration.",
        )

    @staticmethod
    def _deterministic_review(
        plan: Dict[str, Any],
        static_analysis: Dict[str, Any],
        compile_validation: Dict[str, Any],
        package_export: Dict[str, Any],
    ) -> Dict[str, Any]:
        must_review_items: List[str] = [
            "AI 生成结果仅用于辅助测试开发，需由 ATE 工程师复核后再上机使用。"
        ]
        recommendations: List[str] = []
        risk_level = "medium"

        if static_analysis and not static_analysis.get("passed", True):
            must_review_items.append("静态校验未完全通过，需要检查缺失项、TODO 或规则告警。")
            recommendations.append("优先处理静态校验中的必修项，再决定是否进入真实工程。")
            risk_level = "high"

        if compile_validation and not compile_validation.get("passed", True):
            must_review_items.append("编译预检未通过，需要检查宏、API、头文件和资源调用。")
            recommendations.append("根据编译预检首条错误修正代码后，再重新生成或重试。")
            risk_level = "high"
        elif compile_validation.get("mode") == "simulated_compile_check":
            must_review_items.append("当前仅完成模拟编译预检，仍需在真实 STS8200S 工程环境中复核。")

        if plan.get("requires_vector"):
            must_review_items.append("本次生成依赖 VECDIO，请确认向量文件、label 与 time set。")
        if plan.get("requires_pgs"):
            must_review_items.append("本次生成依赖 PGS，请确认函数项和 AutoLoad 参数。")

        if package_export:
            recommendations.append("工程包已导出，可在运行中心查看产物后再进入人工复核。")
        else:
            recommendations.append("如需进一步联调，请导出工程包并检查 vecdio / pgs / sln 产物。")

        return {
            "overall_status": "needs_human_review",
            "summary": "代码骨架已生成，但仍需人工复核测试逻辑、平台调用和工程集成细节。",
            "risk_level": risk_level,
            "must_review_items": must_review_items,
            "recommendations": recommendations,
            "confidence_score": 0.0,
        }


class Module3EngineeringPackageAgent(BaseAgent):
    agent_name = "engineering_packager"

    def __init__(self, testprogram_service: TestProgramService) -> None:
        self.testprogram_service = testprogram_service

    def should_run(self, context: RunContext) -> bool:
        return bool(context.input_payload.get("export_package"))

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        result = context.shared["generated_result"]
        if not payload.get("file_id"):
            return AgentStepResult(
                agent=self.agent_name,
                status="failed",
                message="Engineering package export requires module 1 artifacts.",
                errors=["export_package requires file_id so module 1 artifacts can be resolved."],
                metadata={"http_code": 400, "failure_kind": "missing_file_id"},
            )

        package = self.testprogram_service.export_package(
            file_id=payload["file_id"],
            chip_name=result["chip_name"],
            chip_type=result["chip_type"],
            test_items=result["test_items"],
            code=result["code"],
            user_prompt=payload.get("user_prompt", ""),
            source="codegen",
            generator_mode="engineering_package",
            extra_notes=[
                "This package was exported from /api/v1/codegen/generate.",
                "Use it as the editable bridge between AI generation and STS8200S project integration.",
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


def build_module3_codegen_controller(
    *,
    planner: CodegenPlannerService,
    service: CodegenService,
    static_validator: CodeValidator,
    compile_validator: CompileValidationService,
    testprogram_service: TestProgramService,
    review_service: Optional[ReviewService] = None,
) -> AgentController:
    controller = AgentController()
    controller.register_flow(
        "module3_codegen",
        [
            Module3PlanningAgent(planner),
            Module3AssemblyAgent(service),
            Module3StaticValidationAgent(static_validator),
            Module3CompileValidationAgent(compile_validator),
            Module3ReviewAgent(review_service=review_service),
            Module3EngineeringPackageAgent(testprogram_service),
        ],
    )
    return controller


def finalize_module3_run(
    run,
    knowledge: EnterpriseCodeKnowledgeService,
) -> Dict[str, Any]:
    generated_result = dict(run.shared.get("generated_result") or {})
    if not generated_result:
        return {}
    generated_result["plan"] = run.shared.get("plan")
    generated_result["recommendation"] = run.shared.get("recommendation")
    generated_result["knowledge_summary"] = knowledge.summary()
    generated_result["review"] = run.shared.get("review")
    generated_result["run"] = {
        "run_id": run.run_id,
        "flow_name": run.flow_name,
        "status": run.status,
        "steps": run.steps,
        "warnings": run.warnings,
        "errors": run.errors,
        "artifacts": run.artifacts,
    }
    return generated_result

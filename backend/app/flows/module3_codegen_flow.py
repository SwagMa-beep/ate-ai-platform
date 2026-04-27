"""
Module 3 code-generation flow built on top of the lightweight AgentController.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent, RunContext
from app.services.code_validator import CodeValidator
from app.services.codegen_planner_service import CodegenPlannerService
from app.services.codegen_service import CodegenService
from app.services.compile_validation_service import CompileValidationService
from app.services.enterprise_code_knowledge import EnterpriseCodeKnowledgeService
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
            output={"generated_result": result},
            artifacts=[{"type": "compile_validation", "summary": {"passed": compile_analysis.get("passed")}}],
        )


class Module3EngineeringPackageAgent(BaseAgent):
    agent_name = "engineering_packager"

    def __init__(self, testprogram_service: TestProgramService) -> None:
        self.testprogram_service = testprogram_service

    def run(self, context: RunContext) -> AgentStepResult:
        payload = context.input_payload
        result = context.shared["generated_result"]
        if not payload.get("export_package"):
            return AgentStepResult(agent=self.agent_name, status="completed")
        if not payload.get("file_id"):
            return AgentStepResult(
                agent=self.agent_name,
                status="failed",
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
) -> AgentController:
    controller = AgentController()
    controller.register_flow(
        "module3_codegen",
        [
            Module3PlanningAgent(planner),
            Module3AssemblyAgent(service),
            Module3StaticValidationAgent(static_validator),
            Module3CompileValidationAgent(compile_validator),
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


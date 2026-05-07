from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent
from app.flows.module3_codegen_flow import build_module3_codegen_controller, finalize_module3_run
from app.services.code_validator import CodeValidator
from app.services.codegen_planner_service import CodegenPlannerService
from app.services.codegen_service import CodegenService
from app.services.compile_validation_service import CompileValidationService
from app.services.enterprise_code_knowledge import get_enterprise_code_knowledge_service
from app.services.testprogram_service import TestProgramService


def _build_controller():
    return build_module3_codegen_controller(
        planner=CodegenPlannerService(),
        service=CodegenService(),
        static_validator=CodeValidator(),
        compile_validator=CompileValidationService(),
        testprogram_service=TestProgramService(),
    )


def test_module3_agent_controller_completes_codegen_flow():
    controller = _build_controller()
    knowledge = get_enterprise_code_knowledge_service()
    recommendation = {
        "chip_type": "digital",
        "recommended_items": ["CON", "FUN"],
        "optional_items": [],
        "detected_params": [],
        "reason_summary": [],
        "scenario": "digital",
        "source": "manual",
    }

    run = controller.run_flow(
        flow_name="module3_codegen",
        payload={
            "chip_name": "HD74LS00P",
            "chip_type": "digital",
            "test_items": ["CON", "FUN"],
            "user_prompt": "",
            "vcc": 5.0,
            "vout": 3.3,
            "ldo_out_pin": 2,
            "load_ma": 100.0,
            "pin_names": ["A1", "B1", "Y1", "VCC", "GND"],
            "input_pins": ["A1", "B1"],
            "output_pins": ["Y1"],
            "export_package": False,
        },
        initial_shared={
            "recommendation": recommendation,
            "selected_test_items": ["CON", "FUN"],
        },
    )

    result = finalize_module3_run(run, knowledge)
    assert run.status == "human_review_required"
    assert result["filename"] == "HD74LS00P_test.cpp"
    assert result["plan"]["scenario"] == "digital"
    assert result["compile_validation"]["attempted"] is True
    assert result["run"]["steps"][0]["agent"] == "codegen_planner"
    assert result["review"]["overall_status"] == "needs_human_review"
    assert result["run"]["steps"][4]["agent"] == "review_agent"


def test_module3_agent_controller_stops_on_blocking_plan():
    controller = _build_controller()

    run = controller.run_flow(
        flow_name="module3_codegen",
        payload={
            "chip_name": "HD74LS00P",
            "chip_type": "digital",
            "test_items": ["VOH"],
            "user_prompt": "",
            "vcc": 5.0,
            "vout": 3.3,
            "ldo_out_pin": 2,
            "load_ma": 100.0,
            "pin_names": ["A1", "B1", "VCC", "GND"],
            "input_pins": ["A1", "B1"],
            "output_pins": [],
            "export_package": False,
        },
        initial_shared={
            "recommendation": {"chip_type": "digital"},
            "selected_test_items": ["VOH"],
        },
    )

    assert run.status == "failed"
    assert run.shared["plan"]["errors"]
    assert run.steps[0]["metadata"]["failure_kind"] == "blocking_constraints"


class _SkipAgent(BaseAgent):
    agent_name = "skip_agent"

    def should_run(self, context):
        return False

    def run(self, context):
        raise AssertionError("skip agent should never run")


class _RetryAgent(BaseAgent):
    agent_name = "retry_agent"

    def __init__(self):
        self.calls = 0

    def max_retries(self) -> int:
        return 1

    def run(self, context):
        self.calls += 1
        if self.calls == 1:
            return AgentStepResult(agent=self.agent_name, status="failed", errors=["transient"])
        return AgentStepResult(agent=self.agent_name, status="completed", message="retried successfully")


class _ReviewAgent(BaseAgent):
    agent_name = "review_agent"

    def run(self, context):
        return AgentStepResult(
            agent=self.agent_name,
            status="warning",
            warnings=["manual review required"],
            requires_human_review=True,
        )


def test_agent_controller_supports_skip_retry_and_human_review():
    controller = AgentController()
    controller.register_flow("demo", [_SkipAgent(), _RetryAgent(), _ReviewAgent()])

    run = controller.run_flow(flow_name="demo", payload={})

    assert run.status == "human_review_required"
    assert run.steps[0]["status"] == "skipped"
    assert run.steps[0]["metadata"]["started_at"]
    assert run.steps[0]["metadata"]["finished_at"]
    assert run.steps[0]["metadata"]["duration_seconds"] == 0.0
    assert run.steps[1]["metadata"]["retries_used"] == 1
    assert run.steps[1]["metadata"]["started_at"]
    assert run.steps[1]["metadata"]["finished_at"]
    assert isinstance(run.steps[1]["metadata"]["duration_seconds"], float)
    assert run.steps[2]["requires_human_review"] is True
    assert run.steps[2]["metadata"]["started_at"]
    assert run.steps[2]["metadata"]["finished_at"]

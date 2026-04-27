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
    assert run.status == "completed"
    assert result["filename"] == "HD74LS00P_test.cpp"
    assert result["plan"]["scenario"] == "digital"
    assert result["compile_validation"]["attempted"] is True
    assert result["run"]["steps"][0]["agent"] == "codegen_planner"


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


from app.services.codegen_service import CodegenService
from app.services.codegen_planner_service import CodegenPlannerService


def test_codegen_uses_templates_without_llm_call():
    result = CodegenService().generate(
        chip_name="HD74LS00P",
        chip_type="digital",
        test_items=["CON", "FUN"],
        user_prompt="",
        pin_names=["A1", "B1", "Y1", "VCC", "GND"],
        input_pins=["A1", "B1"],
        output_pins=["Y1"],
        vcc=5.0,
    )

    assert result["filename"] == "HD74LS00P_test.cpp"
    assert result["functions"] == 2
    assert 'DUT_API int CON' in result["code"]
    assert 'DUT_API int FUN' in result["code"]
    assert 'vector<string> InputPin_String = { "A1", "B1" }' in result["code"]
    assert 'PMU_VRANG_10V' in result["code"]
    assert 'PMU_IRANG_1MA' in result["code"]
    assert 'pmu.SetAndMeas(AllPin_Int[i], FIMV, -100e-6, PMU_VRANG_10V, PMU_IRANG_1MA);' in result["code"]
    assert result["retrieved_chunks"] == []


def test_codegen_can_use_enterprise_knowledge_for_extended_items():
    result = CodegenService().generate(
        chip_name="HD74LS00P",
        chip_type="digital",
        test_items=["VIK", "TP1"],
        user_prompt="",
        pin_names=["A1", "B1", "Y1", "VCC", "GND"],
        input_pins=["A1", "B1"],
        output_pins=["Y1"],
        vcc=5.0,
    )

    assert 'DUT_API int VIK' in result["code"]
    assert 'DUT_API int TP1' in result["code"]
    assert 'QTMU_PLUS tmu0(0);' in result["code"]
    assert 'PMU_VRANG_5V' in result["code"] or 'PMU_VRANG_10V' in result["code"]
    assert result["knowledge_used"] is True


def test_codegen_planner_builds_constraints_and_sources():
    plan = CodegenPlannerService().build_plan(
        chip_name="HD74LS00P",
        chip_type="digital",
        test_items=["FUN", "VOH"],
        pin_names=["A1", "B1", "Y1", "VCC", "GND"],
        input_pins=["A1", "B1"],
        output_pins=["Y1"],
        vcc=5.0,
    )

    assert plan["scenario"] == "digital"
    assert plan["requires_vector"] is True
    assert "UserDIO" in plan["resources"]
    assert plan["items"][0]["template_source"] in {"built_in", "enterprise_sample"}
    assert plan["errors"] == []
    assert plan["warnings"] == []


def test_codegen_planner_blocks_invalid_digital_ldo_mix():
    plan = CodegenPlannerService().build_plan(
        chip_name="HD74LS00P",
        chip_type="digital",
        test_items=["LDO_DROPOUT"],
        pin_names=["A1", "B1", "Y1", "VCC", "GND"],
        input_pins=["A1", "B1"],
        output_pins=["Y1"],
        vcc=5.0,
    )

    assert plan["errors"]
    assert any("LDO" in message for message in plan["errors"])


def test_codegen_planner_blocks_missing_output_for_voh():
    plan = CodegenPlannerService().build_plan(
        chip_name="HD74LS00P",
        chip_type="digital",
        test_items=["VOH"],
        pin_names=["A1", "B1", "VCC", "GND"],
        input_pins=["A1", "B1"],
        output_pins=[],
        vcc=5.0,
    )

    assert any("output_pins" in message for message in plan["errors"])

from app.services.codegen_service import CodegenService


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
    assert result["retrieved_chunks"] == []

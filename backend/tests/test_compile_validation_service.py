from app.services.codegen_service import CodegenService
from app.services.compile_validation_service import CompileValidationService


def test_compile_validation_accepts_generated_code():
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

    compile_result = CompileValidationService().validate(result["code"], filename=result["filename"])
    assert compile_result["attempted"] is True
    assert compile_result["passed"] is True


def test_compile_validation_accepts_enterprise_range_aliases():
    code = """
#include "stdafx.h"
#include "UserClass.h"

DUT_API int VIK(short funcindex, LPCTSTR funclabel)
{
    FOVI vcc1(8, "vcc1");
    double value = pmu.SetAndMeas(0, FIMV, -18e-3, VRNG_5V, IRNG_100MA);
    vcc1.Set(FV, 5.0f, FOVI_10V, FOVI_100MA, RELAY_ON);
    VOUT.Set(FI, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
    return value > 0 ? 0 : 0;
}
"""
    compile_result = CompileValidationService().validate(code, filename="range_alias_test.cpp")
    assert compile_result["attempted"] is True
    assert compile_result["passed"] is True

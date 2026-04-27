import json
from pathlib import Path

from app.main import app
from app.services.testprogram_service import TestProgramService as ModuleTestProgramService


def test_testprogram_service_exports_engineering_package(tmp_path):
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir(parents=True)
    testplan_path = processed_dir / "abc123_TestPlan.json"
    testplan_path.write_text(
        json.dumps(
            {
                "chip_name": "HD74LS00P",
                "chip_type": "DIGITAL_74",
                "parameters": [
                    {"param_name": "CON"},
                    {"param_name": "FUN"},
                    {"param_name": "VIH"},
                ],
                "pin_definitions": [
                    {"pin_no": 1, "pin_name": "A1", "direction": "IN", "function": "Input A"},
                    {"pin_no": 2, "pin_name": "B1", "direction": "IN", "function": "Input B"},
                    {"pin_no": 3, "pin_name": "Y1", "direction": "OUT", "function": "Output Y"},
                    {"pin_no": 14, "pin_name": "VCC", "direction": "PWR", "function": "Power"},
                    {"pin_no": 7, "pin_name": "GND", "direction": "GND", "function": "Ground"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    from app.services import testprogram_service as service_module

    original_processed_dir = service_module.settings.PROCESSED_DIR
    service_module.settings.PROCESSED_DIR = processed_dir

    try:
        service = ModuleTestProgramService()
        result = service.export_package(
            file_id="abc123",
            chip_name="HD74LS00P",
            chip_type="DIGITAL_74",
            test_items=["CON", "FUN"],
            code='DUT_API int CON(short funcindex, LPCTSTR funclabel)\n{\n    return 0;\n}\n',
            user_prompt="",
        )
    finally:
        service_module.settings.PROCESSED_DIR = original_processed_dir

    assert result.function_count == 2
    assert result.test_items == ["CON", "FUN"]
    assert Path(result.output_dir).exists()
    assert result.package_zip is not None
    assert Path(result.package_zip).exists()
    assert result.download_url == f"/api/v1/testprogram/package/{result.generation_id}/download"

    generated = {item.file_type: item for item in result.generated_files}
    assert "test_cpp" in generated
    assert generated["test_cpp"].relative_path == "source/test.cpp"
    assert Path(generated["test_cpp"].path).read_text(encoding="utf-8").startswith("DUT_API int CON")
    assert "vector_plan_json" in generated
    vector_plan = json.loads(Path(generated["vector_plan_json"].path).read_text(encoding="utf-8"))
    assert vector_plan["vector_file"] == "HD74LS00P.vecdio"
    assert vector_plan["labels"][0]["test_item"] == "CON"
    assert vector_plan["site_plan"][0]["site"] == "SITE1"
    assert vector_plan["time_sets"][0]["name"] == "TS0"
    assert vector_plan["pattern_sets"][0]["test_item"] == "CON"
    if "vecdio_template" in generated:
        assert generated["vecdio_template"].relative_path == "HD74LS00P.vecdio"
    assert "vs_solution" in generated
    assert generated["vs_solution"].relative_path == "source/HD74LS00P.sln"
    assert "vs_project" in generated
    assert generated["vs_project"].relative_path == "source/HD74LS00P.vcxproj"
    assert "stdafx_h" in generated
    assert generated["stdafx_h"].relative_path == "source/StdAfx.h"
    assert "pgs_plan_json" in generated
    pgs_plan = json.loads(Path(generated["pgs_plan_json"].path).read_text(encoding="utf-8"))
    assert pgs_plan["pgs_file"] == "HD74LS00P.pgs"
    assert pgs_plan["test_items"] == ["CON", "FUN"]
    assert pgs_plan["function_summary"][0]["test_name"] == "CON"
    assert pgs_plan["hook_suggestions"][0]["hook"] == "UserLoad"
    if "pgs_template" in generated:
        assert generated["pgs_template"].relative_path == "HD74LS00P.pgs"

    manifest = json.loads(Path(generated["manifest_json"].path).read_text(encoding="utf-8"))
    assert manifest["chip_name"] == "HD74LS00P"
    assert manifest["test_items"] == ["CON", "FUN"]
    assert "source/test.cpp" in manifest["outputs"]
    assert "source/HD74LS00P.sln" in manifest["outputs"]
    assert "pgs_plan.json" in manifest["outputs"]
    assert result.package_validation["attempted"] is True
    assert result.package_validation["checks"]
    check_map = {item["name"]: item["passed"] for item in result.package_validation["checks"]}
    assert check_map["solution"] is True
    assert check_map["vcxproj"] is True
    assert check_map["project_compiles_test_cpp"] is True
    assert "build_validation" in result.package_validation


def test_testprogram_route_is_mounted():
    paths = {route.path for route in app.routes}
    assert "/api/v1/testprogram/generate" in paths
    assert "/api/v1/testprogram/requirements" in paths
    assert "/api/v1/testprogram/package/{generation_id}/download" in paths

import json

import app.services.testplan_service as service_module
from app.services.testplan_service import TestPlanService as PlanService


def test_detect_chip_type_locally_for_common_families():
    assert PlanService._detect_chip_type_locally("Renesas-HD74LS00P", []) == "DIGITAL_74"
    assert PlanService._detect_chip_type_locally(
        "AT24C02",
        [{"content": "Serial EEPROM with I2C interface, SDA and SCL pins"}],
    ) == "EEPROM"
    assert PlanService._detect_chip_type_locally(
        "L7805CV",
        [{"content": "Positive voltage regulator"}],
    ) == "LDO"


def test_cache_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module.settings, "PROCESSED_DIR", tmp_path)
    cache_key = "abc123"
    excel_path = tmp_path / "chip_TestPlan.xlsx"
    json_path = tmp_path / "chip_TestPlan.json"
    excel_path.write_bytes(b"xlsx")
    json_path.write_text(
        json.dumps(
            {
                "chip_name": "HD74LS00P",
                "chip_type": "DIGITAL_74",
                "test_scenario": "DIGITAL",
                "sts_report": {"is_compatible": True},
                "pin_definitions": [
                    {
                        "pin_no": 14,
                        "pin_name": "VCC",
                        "function": "VCC",
                        "direction": "PWR",
                        "voltage_max": None,
                        "current_max": None,
                        "notes": "",
                    }
                ],
                "statistics": {
                    "total": 21,
                    "A_class": 12,
                    "B_class": 4,
                    "C_class": 4,
                    "blocked": 1,
                    "dc_test_items": 13,
                    "ac_test_items": 2,
                    "ldo_test_items": 0,
                },
                "parameters": [],
            }
        ),
        encoding="utf-8",
    )

    PlanService._save_cached_result(cache_key, excel_path, json_path)
    excel_path.unlink()
    json_path.unlink()

    result = PlanService._load_cached_result(
        cache_key=cache_key,
        chip_name="fallback",
        excel_path=excel_path,
        json_path=json_path,
    )

    assert result is not None
    assert result.status == "success"
    assert result.chip_name == "HD74LS00P"
    assert result.total_params == 21
    assert result.ac_test_items == 2
    assert result.pin_definitions[0].pin_name == "VCC"
    assert result.parameters == []
    assert excel_path.read_bytes() == b"xlsx"
    assert json.loads(json_path.read_text(encoding="utf-8"))["chip_type"] == "DIGITAL_74"


def test_extraction_result_model_dump_keeps_parameters():
    from app.models.testplan import DCParam, ExtractionResult

    result = ExtractionResult(
        status="success",
        chip_name="HD74LS00P",
        chip_type="DIGITAL_74",
        parameters=[
            DCParam(
                param_name="VIH",
                category="A",
                test_scenario="DIGITAL_DC",
                condition="VCC=5V",
                min_val=2.0,
                max_val=5.5,
                unit="V",
            )
        ],
    )

    payload = result.model_dump()
    assert payload["parameters"]
    assert payload["parameters"][0]["param_name"] == "VIH"


def test_validation_messages_are_summarized_for_successful_extraction():
    messages = PlanService._summarize_validation_messages(
        ["无任何数值; ", "无任何数值; ", "下限大于上限; "],
        ["缺少单位; "],
        ["Si单位异常，预期为mV/%等; "],
        blocked_warning="已拦截 3 条无效参数，请复核空值行、上下限和单位。",
    )

    assert messages[0] == "已拦截 3 条无效参数，请复核空值行、上下限和单位。"
    assert "缺少单位" in messages
    assert "Si单位异常，预期为mV/%等" in messages
    assert "2 条参数因无有效数值被拦截。" in messages
    assert "1 条参数因下限大于上限被拦截。" in messages

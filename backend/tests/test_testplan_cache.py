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
    assert excel_path.read_bytes() == b"xlsx"
    assert json.loads(json_path.read_text(encoding="utf-8"))["chip_type"] == "DIGITAL_74"

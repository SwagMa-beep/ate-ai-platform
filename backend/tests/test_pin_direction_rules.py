from app.services.llm_extractor import LLMExtractor
from app.services.testplan_service import TestPlanService


def test_testplan_service_recognizes_common_power_pin_aliases():
    assert TestPlanService._pin_direction("VIN") == "PWR"
    assert TestPlanService._pin_direction("AVDD") == "PWR"
    assert TestPlanService._pin_direction("VBAT") == "PWR"
    assert TestPlanService._pin_direction("VSS") == "GND"
    assert TestPlanService._pin_direction("PGND") == "GND"


def test_llm_extractor_normalize_payload_repairs_pin_directions_from_names():
    payload = {
        "chip_name": "Demo",
        "chip_type": "LDO",
        "dc_params": [],
        "pin_definitions": [
            {"pin_no": 1, "pin_name": "VIN", "direction": "IN", "function": ""},
            {"pin_no": 2, "pin_name": "PGND", "direction": "IN", "function": ""},
            {"pin_no": 3, "pin_name": "VOUT", "direction": "IN", "function": ""},
        ],
    }

    normalized = LLMExtractor._normalize_payload(payload)
    assert normalized["pin_definitions"][0]["direction"] == "PWR"
    assert normalized["pin_definitions"][1]["direction"] == "GND"
    assert normalized["pin_definitions"][2]["direction"] == "OUT"

from app.services.llm_extractor import LLMExtractor


def test_normalize_payload_defaults_missing_lists():
    payload = LLMExtractor._normalize_payload({"chip_type": "bad_type"})

    assert payload["chip_name"] == ""
    assert payload["chip_type"] == "UNKNOWN"
    assert payload["dc_params"] == []
    assert payload["pin_definitions"] == []


def test_normalize_payload_sanitizes_params_and_pins():
    payload = LLMExtractor._normalize_payload(
        {
            "chip_name": None,
            "chip_type": "digital_74",
            "dc_params": [
                {
                    "param_name": " VIH ",
                    "category": "Z",
                    "test_scenario": "bad",
                    "condition": None,
                    "min_val": "",
                    "typ_val": "2.0",
                    "max_val": "-",
                    "unit": None,
                },
                {"param_name": ""},
            ],
            "pin_definitions": [
                {
                    "pin_no": "14",
                    "pin_name": None,
                    "function": " supply ",
                    "direction": "power",
                    "voltage_max": "",
                    "notes": None,
                },
                {"pin_no": "x", "pin_name": "bad"},
            ],
        }
    )

    assert payload["chip_name"] == ""
    assert payload["chip_type"] == "DIGITAL_74"
    assert len(payload["dc_params"]) == 1
    assert payload["dc_params"][0]["param_name"] == "VIH"
    assert payload["dc_params"][0]["category"] == "A"
    assert payload["dc_params"][0]["test_scenario"] == "GENERAL"
    assert payload["dc_params"][0]["condition"] == ""
    assert payload["dc_params"][0]["min_val"] is None
    assert payload["dc_params"][0]["max_val"] is None
    assert payload["dc_params"][0]["unit"] == ""

    assert len(payload["pin_definitions"]) == 1
    assert payload["pin_definitions"][0]["pin_no"] == 14
    assert payload["pin_definitions"][0]["pin_name"] == ""
    assert payload["pin_definitions"][0]["function"] == "supply"
    assert payload["pin_definitions"][0]["direction"] == "IN"
    assert payload["pin_definitions"][0]["voltage_max"] is None
    assert payload["pin_definitions"][0]["notes"] == ""

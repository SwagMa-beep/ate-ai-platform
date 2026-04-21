import json
from pathlib import Path

import pytest


HD74_JSON = Path("data/processed/Renesas-HD74LS00P_TestPlan.json")

EXPECTED_PINS = {
    1: ("1A", "IN"),
    2: ("1B", "IN"),
    3: ("1Y", "OUT"),
    4: ("2A", "IN"),
    5: ("2B", "IN"),
    6: ("2Y", "OUT"),
    7: ("GND", "GND"),
    8: ("3Y", "OUT"),
    9: ("3A", "IN"),
    10: ("3B", "IN"),
    11: ("4Y", "OUT"),
    12: ("4A", "IN"),
    13: ("4B", "IN"),
    14: ("VCC", "PWR"),
}

EXPECTED_CORE_DC = {
    ("A", "VIH"): {"min_val": 2.0, "unit": "V"},
    ("A", "VIL"): {"max_val": 0.8, "unit": "V"},
    ("A", "VOH"): {"min_val": 2.7, "unit": "V"},
    ("A", "VOL"): {"max_val": 0.5, "unit": "V"},
    ("A", "IIH"): {"max_val": 20.0, "unit": "uA"},
    ("A", "IIL"): {"max_val": -0.4, "unit": "mA"},
    ("A", "II"): {"max_val": 0.1, "unit": "mA"},
    ("A", "IOS"): {"min_val": -20.0, "max_val": -100.0, "unit": "mA"},
    ("A", "ICCH"): {"typ_val": 0.8, "max_val": 1.6, "unit": "mA"},
    ("A", "ICCL"): {"typ_val": 2.4, "max_val": 4.4, "unit": "mA"},
    ("A", "VIK"): {"max_val": -1.5, "unit": "V"},
}

EXPECTED_VISIBLE_TABLE_PARAMS = {
    **EXPECTED_CORE_DC,
    ("B", "VCC"): {"max_val": 7.0, "unit": "V"},
    ("B", "VIN"): {"max_val": 7.0, "unit": "V"},
    ("B", "PT"): {"max_val": 400.0, "unit": "mW"},
    ("B", "TSTG"): {"min_val": -65.0, "max_val": 150.0, "unit": "C"},
    ("C", "VCC"): {"min_val": 4.75, "typ_val": 5.0, "max_val": 5.25, "unit": "V"},
    ("C", "IOH"): {"max_val": -400.0, "unit": "uA"},
    ("C", "IOL"): {"max_val": 8.0, "unit": "mA"},
    ("C", "TOPR"): {"min_val": -20.0, "typ_val": 25.0, "max_val": 75.0, "unit": "C"},
    ("A", "TPLH"): {"typ_val": 9.0, "max_val": 15.0, "unit": "ns"},
    ("A", "TPHL"): {"typ_val": 10.0, "max_val": 15.0, "unit": "ns"},
}


def _load_snapshot():
    if not HD74_JSON.exists():
        pytest.skip(f"{HD74_JSON} not generated")
    return json.loads(HD74_JSON.read_text(encoding="utf-8"))


def _norm_name(value):
    return str(value or "").upper().replace(" ", "")


def _norm_unit(value):
    unit = str(value or "").replace("µ", "u").replace("μ", "u")
    unit = unit.replace("碌", "u").replace("℃", "C").replace("°C", "C")
    return unit.strip()


def _param_index(parameters):
    index = {}
    for param in parameters:
        key = (_norm_name(param.get("category")), _norm_name(param.get("param_name")))
        index.setdefault(key, []).append(param)
    return index


def _matches_expected(actual, expected):
    actual_unit = _norm_unit(actual.get("unit"))
    expected_unit = expected.get("unit")
    for field, expected_value in expected.items():
        if field == "unit":
            if actual_unit != expected_value and {actual_unit, expected_value} != {"mA", "uA"}:
                return False
            continue
        actual_value = actual.get(field)
        if actual_value is None:
            return False
        actual_float = float(actual_value)
        if actual_unit == "mA" and expected_unit == "uA":
            actual_float *= 1000.0
        elif actual_unit == "uA" and expected_unit == "mA":
            actual_float /= 1000.0
        if abs(actual_float - expected_value) > 1e-6:
            return False
    return True


def _score_params(parameters, expected):
    index = _param_index(parameters)
    found = []
    value_matched = []
    missing = []
    wrong_value = []

    for key, expected_values in expected.items():
        candidates = index.get(key, [])
        if not candidates:
            missing.append(key)
            continue
        found.append(key)
        if any(_matches_expected(candidate, expected_values) for candidate in candidates):
            value_matched.append(key)
        else:
            wrong_value.append(key)

    return {
        "found": found,
        "value_matched": value_matched,
        "missing": missing,
        "wrong_value": wrong_value,
    }


def test_hd74_quality_snapshot():
    data = _load_snapshot()

    pin_index = {
        int(pin["pin_no"]): (_norm_name(pin["pin_name"]), _norm_name(pin["direction"]))
        for pin in data["pin_definitions"]
    }
    pin_hits = [
        pin_no
        for pin_no, expected in EXPECTED_PINS.items()
        if pin_index.get(pin_no) == (_norm_name(expected[0]), _norm_name(expected[1]))
    ]

    core = _score_params(data["parameters"], EXPECTED_CORE_DC)
    visible = _score_params(data["parameters"], EXPECTED_VISIBLE_TABLE_PARAMS)

    pin_recall = len(pin_hits) / len(EXPECTED_PINS)
    core_recall = len(core["found"]) / len(EXPECTED_CORE_DC)
    core_value_accuracy = len(core["value_matched"]) / len(EXPECTED_CORE_DC)
    visible_recall = len(visible["found"]) / len(EXPECTED_VISIBLE_TABLE_PARAMS)
    visible_value_accuracy = len(visible["value_matched"]) / len(EXPECTED_VISIBLE_TABLE_PARAMS)

    print(
        "\nHD74 quality snapshot\n"
        f"- pin exact recall: {len(pin_hits)}/{len(EXPECTED_PINS)} = {pin_recall:.1%}\n"
        f"- core DC recall: {len(core['found'])}/{len(EXPECTED_CORE_DC)} = {core_recall:.1%}\n"
        f"- core DC value accuracy: {len(core['value_matched'])}/{len(EXPECTED_CORE_DC)} = {core_value_accuracy:.1%}\n"
        f"- visible table recall: {len(visible['found'])}/{len(EXPECTED_VISIBLE_TABLE_PARAMS)} = {visible_recall:.1%}\n"
        f"- visible table value accuracy: {len(visible['value_matched'])}/{len(EXPECTED_VISIBLE_TABLE_PARAMS)} = {visible_value_accuracy:.1%}\n"
        f"- missing visible params: {visible['missing']}\n"
        f"- wrong-value visible params: {visible['wrong_value']}"
    )
    assert pin_recall == 1.0
    assert core_recall == 1.0
    assert core_value_accuracy == 1.0
    assert visible_recall >= 0.8
    assert visible_value_accuracy >= 0.8

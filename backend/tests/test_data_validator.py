import pandas as pd

from app.services.data_validator import DataValidator


def make_df(rows):
    defaults = {
        "param_name": "VOH",
        "condition": "VCC=5V",
        "category": "A",
        "min_val": 2.7,
        "typ_val": None,
        "max_val": 5.0,
        "unit": "V",
        "confidence": 0.9,
        "sts_test_function": "",
        "test_pin": "Y1",
    }
    return pd.DataFrame([{**defaults, **row} for row in rows])


def test_validator_blocks_invalid_numeric_ranges():
    df = make_df([
        {"param_name": "VOH", "min_val": 5.0, "max_val": 2.7},
        {"param_name": "VOL", "min_val": None, "typ_val": None, "max_val": None},
    ])

    result = DataValidator().clean_and_validate(df, chip_type="DIGITAL_74")

    assert result["Status"].tolist() == ["已拦截", "已拦截"]
    assert "下限大于上限" in result.loc[0, "Validation_Error"]
    assert "无任何数值" in result.loc[1, "Validation_Error"]


def test_validator_marks_low_confidence_for_manual_review():
    df = make_df([
        {"param_name": "VIH", "confidence": 0.5},
    ])

    result = DataValidator().clean_and_validate(df, chip_type="DIGITAL_74")

    assert result.loc[0, "Status"] == "需人工确认"
    assert "置信度低" in result.loc[0, "Validation_Error"]


def test_validator_reports_sts_voltage_range_warning():
    df = make_df([
        {"param_name": "VIN", "max_val": 12.0, "unit": "V", "category": "C"},
    ])

    result = DataValidator().clean_and_validate(df, chip_type="LDO")

    assert "电压超出VI源量程" in result.loc[0, "STS_Warning"]

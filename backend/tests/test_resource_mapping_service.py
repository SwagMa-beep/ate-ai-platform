import pandas as pd

from app.models.testplan import ExtractionResult
from app.services.resource_mapping_service import ResourceMappingService


def test_resource_mapping_supports_extended_dio_and_bidir_warning():
    service = ResourceMappingService()
    extraction_result = ExtractionResult(
        status="success",
        chip_name="WideBusChip",
        chip_type="DIGITAL_74",
        test_scenario="A",
        total_params=0,
        a_params=0,
        b_params=0,
        c_params=0,
    )
    pin_rows = [
        {"pin_no": 1, "pin_name": "VCC", "direction": "PWR", "function": "power"},
        {"pin_no": 2, "pin_name": "VCCA", "direction": "PWR", "function": "analog power"},
        {"pin_no": 3, "pin_name": "GND", "direction": "GND", "function": "ground"},
    ]
    for index in range(4, 20):
        pin_rows.append(
            {
                "pin_no": index,
                "pin_name": f"IO{index}",
                "direction": "BIDIR" if index == 4 else "IN",
                "function": "signal",
            }
        )

    result = service.generate_resource_map(extraction_result, pd.DataFrame(pin_rows), dual_site=False)

    assert result.status == "success"
    dio_mappings = [item for item in result.resource_mappings if item.resource_type == "DIO"]
    assert max(item.channel_no for item in dio_mappings) >= 12
    bidir_mapping = next(item for item in dio_mappings if item.pin_name == "IO4")
    assert bidir_mapping.force_mode == "DIO_Drive"
    assert bidir_mapping.measure_mode == "DIO_Sense"
    assert any("双向引脚" in warning for warning in result.warnings)
    assert any("电源类引脚" in warning for warning in result.warnings)


def test_resource_mapping_general_prefers_dio_for_signal_pins():
    service = ResourceMappingService()
    extraction_result = ExtractionResult(
        status="success",
        chip_name="MixedChip",
        chip_type="UNKNOWN_CUSTOM",
        test_scenario="C",
        total_params=0,
        a_params=0,
        b_params=0,
        c_params=0,
    )
    pin_rows = [
        {"pin_no": 1, "pin_name": "VIN", "direction": "PWR", "function": "input supply", "voltage_max": 12},
        {"pin_no": 2, "pin_name": "GPIO", "direction": "BIDIR", "function": "general io"},
        {"pin_no": 3, "pin_name": "ALERT", "direction": "OUT", "function": "status"},
        {"pin_no": 4, "pin_name": "GND", "direction": "GND", "function": "ground"},
    ]

    result = service.generate_resource_map(extraction_result, pd.DataFrame(pin_rows), dual_site=False)

    assert result.status == "success"
    gpio = next(item for item in result.resource_mappings if item.pin_name == "GPIO")
    alert = next(item for item in result.resource_mappings if item.pin_name == "ALERT")
    vin = next(item for item in result.resource_mappings if item.pin_name == "VIN")
    assert gpio.resource_type == "DIO"
    assert gpio.measure_mode == "DIO_Sense"
    assert alert.resource_type == "DIO"
    assert vin.resource_type == "FH_SH"

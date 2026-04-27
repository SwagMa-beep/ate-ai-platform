import pandas as pd

from app.flows.module2_resource_map_flow import build_module2_resource_map_controller
from app.models.resource_map import AdapterInfo, PinGroupConfig, ResourceMapResult
from app.models.testplan import ExtractionResult
from app.services.resource_mapping_service import ResourceMappingService


def test_module2_agent_controller_completes_mapping_flow(monkeypatch):
    def fake_generate(self, extraction_result, pin_mapping_df, dual_site=False):
        return ResourceMapResult(
            status="success",
            chip_name="HD74LS00P",
            chip_type="DIGITAL_74",
            adapter_model="CBIT128",
            resource_mappings=[],
            pgs_configs=[],
            pgs_detail_conditions=[],
            pin_groups=PinGroupConfig(
                chip_name="HD74LS00P",
                pin_count=2,
                vector_file="HD74LS00P.vecdio",
                all_group=["A1", "Y1"],
                in_group=["A1"],
                out_group=["Y1"],
                pwr_group=[],
                gnd_group=[],
            ),
            adapter_info=AdapterInfo(
                adapter_model="CBIT128",
                chip_type="DIGITAL_74",
                socket_type="ZIF14",
                max_pin_count=14,
                vi_channels=["FH0", "SH0"],
                dio_channels=["DIO0", "DIO1"],
                cbit_channels=["CBIT0"],
                tmu_channels=["TMUA"],
                bom_items=[],
                notes="demo",
            ),
            warnings=["check rail assignment"],
        )

    monkeypatch.setattr(ResourceMappingService, "generate_resource_map", fake_generate)

    controller = build_module2_resource_map_controller(service=ResourceMappingService())
    run = controller.run_flow(
        flow_name="module2_resource_map",
        payload={
            "file_id": "abc12345",
            "chip_type": "DIGITAL_74",
            "dual_site": False,
            "extraction_result": ExtractionResult(status="success", chip_name="HD74LS00P", chip_type="DIGITAL_74"),
            "pin_mapping_df": pd.DataFrame([{"pin_no": 1, "pin_name": "A1", "direction": "IN"}]),
        },
    )

    assert run.status == "completed"
    assert run.steps[0]["agent"] == "mapping_input_resolver"
    assert run.steps[1]["agent"] == "resource_mapper"
    assert run.artifacts[1]["type"] == "resource_mapping"


def test_module2_agent_controller_stops_on_mapping_failure(monkeypatch):
    def fake_generate(self, extraction_result, pin_mapping_df, dual_site=False):
        return ResourceMapResult(status="error", chip_name="HD74LS00P", chip_type="DIGITAL_74", errors=["adapter unavailable"])

    monkeypatch.setattr(ResourceMappingService, "generate_resource_map", fake_generate)

    controller = build_module2_resource_map_controller(service=ResourceMappingService())
    run = controller.run_flow(
        flow_name="module2_resource_map",
        payload={
            "file_id": "abc12345",
            "chip_type": "DIGITAL_74",
            "dual_site": False,
            "extraction_result": ExtractionResult(status="success", chip_name="HD74LS00P", chip_type="DIGITAL_74"),
            "pin_mapping_df": pd.DataFrame([{"pin_no": 1, "pin_name": "A1", "direction": "IN"}]),
        },
    )

    assert run.status == "failed"
    assert run.errors == ["adapter unavailable"]
    assert run.steps[-1]["metadata"]["failure_kind"] == "resource_mapping_failed"

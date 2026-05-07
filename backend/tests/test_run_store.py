from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from app.services.run_store import RunStore


def test_run_store_save_and_reload(tmp_path):
    store = RunStore()
    store.base_dir = tmp_path
    store.base_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_id": "module3_codegen_demo1234",
        "flow_name": "module3_codegen",
        "status": "completed",
        "created_at": "2026-04-26T00:00:00",
        "updated_at": "2026-04-26T00:00:01",
        "input_payload": {"chip_name": "HD74LS00P"},
        "steps": [{"agent": "codegen_planner", "status": "completed"}],
        "artifacts": [{"type": "codegen_plan"}],
        "warnings": [],
        "errors": [],
        "shared": {"plan": {"selected_items": ["CON"]}},
    }

    store.save_run(payload)
    loaded = store.get_run(payload["run_id"])
    artifacts = store.get_artifacts(payload["run_id"])
    artifact = store.get_artifact(payload["run_id"], "codegen_plan_1")

    assert loaded is not None
    assert loaded["run_id"] == payload["run_id"]
    assert loaded["artifacts"][0]["type"] == "codegen_plan"
    assert (tmp_path / payload["run_id"] / "run.json").exists()
    assert (tmp_path / payload["run_id"] / "steps.json").exists()
    assert (tmp_path / payload["run_id"] / "artifacts" / "index.json").exists()
    assert artifacts[0]["name"] == "codegen_plan_1"
    assert artifact is not None
    assert artifact["type"] == "codegen_plan"


def test_run_store_serializes_runtime_objects(tmp_path):
    class DemoModel(BaseModel):
        chip_name: str
        total_params: int

    store = RunStore()
    store.base_dir = tmp_path
    store.base_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_id": "module2_resource_map_demo5678",
        "flow_name": "module2_resource_map",
        "status": "completed",
        "created_at": datetime(2026, 5, 6, 14, 30, 0).isoformat(),
        "updated_at": datetime(2026, 5, 6, 14, 30, 1),
        "input_payload": {
            "extraction_result": DemoModel(chip_name="HD74LS00P", total_params=14),
            "pin_mapping_df": pd.DataFrame([{"pin_no": 1, "pin_name": "A"}]),
            "processed_dir": Path("D:/software/ate-ai-platform/data/processed"),
        },
        "steps": [{"agent": "resource_mapper", "status": "completed"}],
        "artifacts": [{"type": "resource_mapping"}],
        "warnings": [],
        "errors": [],
        "shared": {"summary": {"site_count": 1}},
    }

    store.save_run(payload)
    loaded = store.get_run(payload["run_id"])

    assert loaded is not None
    assert loaded["updated_at"] == "2026-05-06T14:30:01"
    assert loaded["input_payload"]["extraction_result"]["chip_name"] == "HD74LS00P"
    assert loaded["input_payload"]["pin_mapping_df"] == [{"pin_no": 1, "pin_name": "A"}]
    assert loaded["input_payload"]["processed_dir"].replace("\\", "/").endswith("data/processed")


def test_run_store_can_clear_runs_by_flow(tmp_path):
    store = RunStore()
    store.base_dir = tmp_path
    store.base_dir.mkdir(parents=True, exist_ok=True)

    payloads = [
        {
            "run_id": "full_ate_development_demo1",
            "flow_name": "full_ate_development",
            "status": "completed",
            "created_at": "2026-05-06T18:00:00",
            "updated_at": "2026-05-06T18:00:01",
            "steps": [],
            "artifacts": [],
            "warnings": [],
            "errors": [],
            "shared": {},
        },
        {
            "run_id": "post_review_delivery_demo2",
            "flow_name": "post_review_delivery",
            "status": "completed",
            "created_at": "2026-05-06T18:00:00",
            "updated_at": "2026-05-06T18:00:01",
            "steps": [],
            "artifacts": [],
            "warnings": [],
            "errors": [],
            "shared": {},
        },
    ]

    for payload in payloads:
        store.save_run(payload)

    deleted = store.clear_runs(flow_name="full_ate_development")

    assert deleted == 1
    assert store.get_run("full_ate_development_demo1") is None
    assert store.get_run("post_review_delivery_demo2") is not None

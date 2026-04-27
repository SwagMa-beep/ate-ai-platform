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

    assert loaded is not None
    assert loaded["run_id"] == payload["run_id"]
    assert loaded["artifacts"][0]["type"] == "codegen_plan"


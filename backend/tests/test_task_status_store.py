from app.services.task_status_store import TaskStatusStore


def test_task_status_store_persists_payload(tmp_path):
    store = TaskStatusStore()
    store.root = tmp_path / "task_status"
    store.root.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": "processing",
        "progress": 42,
        "message": "working",
        "file_id": "abc123",
    }
    store.set("task001", payload)

    loaded = store.get("task001")
    assert loaded == payload

    updated = store.update("task001", progress=100, status="completed")
    assert updated["progress"] == 100
    assert updated["status"] == "completed"
    assert store.get("task001")["file_id"] == "abc123"


def test_task_status_store_lists_and_prunes(tmp_path):
    store = TaskStatusStore()
    store.root = tmp_path / "task_status"
    store.root.mkdir(parents=True, exist_ok=True)

    store.set("task001", {"task_id": "task001", "status": "completed"})
    store.set("task002", {"task_id": "task002", "status": "failed"})
    store.set("task003", {"task_id": "task003", "status": "processing"})

    items = store.list(limit=10)
    assert len(items) == 3

    deleted = store.prune(statuses={"completed", "failed"})
    assert deleted == 2
    remaining = {item["task_id"] for item in store.list(limit=10)}
    assert remaining == {"task003"}

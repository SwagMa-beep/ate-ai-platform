from app.services import workspace_memory_service as workspace_memory_module


def test_workspace_memory_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_memory_module.settings, "WORKSPACE_MEMORY_PATH", tmp_path / "workspace_memory.json")
    service = workspace_memory_module.WorkspaceMemoryService()

    service.update_testplan_context(
        {
            "file_id": "abc123",
            "file_name": "demo.pdf",
            "chip_name": "HD74LS00P",
            "chip_type": "digital",
            "summary": "HD74LS00P / digital / 参数 10 项 / 引脚 14 个",
        }
    )
    service.update_resource_map_context({"file_name": "map-1", "summary": "资源映射完成"})
    service.update_codegen_context({"template": "FUN,VIH", "summary": "代码 120 行"})
    service.update_failure_context({"topic": "channel-4", "summary": "良率 97%"})
    service.add_note("最近一次运行需要先复核资源映射。")

    memory = service.load_memory()
    assert memory["current_chip"]["name"] == "HD74LS00P"
    assert memory["recent_testplan"]["file_id"] == "abc123"
    assert memory["recent_resource_map"]["summary"] == "资源映射完成"
    assert memory["recent_codegen"]["template"] == "FUN,VIH"
    assert memory["recent_failure_topic"]["topic"] == "channel-4"
    assert memory["notes"]


def test_workspace_memory_reset(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_memory_module.settings, "WORKSPACE_MEMORY_PATH", tmp_path / "workspace_memory.json")
    service = workspace_memory_module.WorkspaceMemoryService()
    service.add_note("temporary")

    reset = service.reset_memory()

    assert reset["current_chip"]["name"] == ""
    assert reset["notes"] == []

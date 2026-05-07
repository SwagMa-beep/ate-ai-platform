"""Workspace-level lightweight memory for the engineer assistant."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _default_memory() -> dict[str, Any]:
    return {
        "current_chip": {"name": "", "chip_type": "", "updated_at": ""},
        "recent_testplan": {"file_id": "", "file_name": "", "summary": "", "updated_at": ""},
        "recent_resource_map": {"file_name": "", "summary": "", "updated_at": ""},
        "recent_codegen": {"template": "", "summary": "", "updated_at": ""},
        "recent_failure_topic": {"topic": "", "summary": "", "updated_at": ""},
        "notes": [],
    }


def _clean_text_for_memory(text: Any) -> str:
    clean = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    clean = re.sub(r"\s+", " ", clean)
    if not clean:
        return ""
    if "???" in clean and not re.search(r"[\u4e00-\u9fff]", clean):
        return ""
    return clean


class WorkspaceMemoryService:
    def __init__(self):
        settings.create_dirs()

    def load_memory(self) -> dict[str, Any]:
        path = settings.WORKSPACE_MEMORY_PATH
        if not path.exists():
            data = _default_memory()
            self.save_memory(data)
            return data
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            merged = _default_memory()
            merged.update(data or {})
            return merged
        except Exception as exc:
            logger.warning(f"Failed to load workspace memory, resetting file: {exc}")
            data = _default_memory()
            self.save_memory(data)
            return data

    def save_memory(self, data: dict[str, Any]) -> None:
        path = settings.WORKSPACE_MEMORY_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset_memory(self) -> dict[str, Any]:
        data = _default_memory()
        self.save_memory(data)
        return data

    def update_chip_context(self, chip_name: str, chip_type: str | None = None) -> None:
        chip_name = _clean_text_for_memory(chip_name)
        if not chip_name:
            return
        data = self.load_memory()
        data["current_chip"] = {
            "name": chip_name,
            "chip_type": _clean_text_for_memory(chip_type or data.get("current_chip", {}).get("chip_type") or ""),
            "updated_at": _now(),
        }
        self.save_memory(data)

    def update_testplan_context(self, payload: dict[str, Any]) -> None:
        data = self.load_memory()
        data["recent_testplan"] = {
            "file_id": _clean_text_for_memory(payload.get("file_id", "")),
            "file_name": _clean_text_for_memory(payload.get("file_name", "")),
            "summary": _clean_text_for_memory(payload.get("summary", "")),
            "updated_at": _now(),
        }
        chip_name = _clean_text_for_memory(payload.get("chip_name", ""))
        chip_type = _clean_text_for_memory(payload.get("chip_type", ""))
        if chip_name:
            data["current_chip"] = {"name": chip_name, "chip_type": chip_type, "updated_at": _now()}
        self.save_memory(data)

    def update_resource_map_context(self, payload: dict[str, Any]) -> None:
        data = self.load_memory()
        data["recent_resource_map"] = {
            "file_name": _clean_text_for_memory(payload.get("file_name", "")),
            "summary": _clean_text_for_memory(payload.get("summary", "")),
            "updated_at": _now(),
        }
        self.save_memory(data)

    def update_codegen_context(self, payload: dict[str, Any]) -> None:
        data = self.load_memory()
        data["recent_codegen"] = {
            "template": _clean_text_for_memory(payload.get("template", "")),
            "summary": _clean_text_for_memory(payload.get("summary", "")),
            "updated_at": _now(),
        }
        self.save_memory(data)

    def update_failure_context(self, payload: dict[str, Any]) -> None:
        data = self.load_memory()
        data["recent_failure_topic"] = {
            "topic": _clean_text_for_memory(payload.get("topic", "")),
            "summary": _clean_text_for_memory(payload.get("summary", "")),
            "updated_at": _now(),
        }
        self.save_memory(data)

    def add_note(self, note: str) -> None:
        clean = _clean_text_for_memory(note)
        if not clean:
            return
        data = self.load_memory()
        notes = list(data.get("notes", []))
        notes.insert(0, {"text": clean[:300], "updated_at": _now()})
        data["notes"] = notes[: settings.WORKSPACE_MEMORY_MAX_ITEMS]
        self.save_memory(data)

    def build_context_summary(self) -> str:
        data = self.load_memory()
        lines: list[str] = ["[当前工作区上下文]"]
        added = False

        chip = data.get("current_chip") or {}
        if chip.get("name"):
            chip_type = chip.get("chip_type") or "未知"
            lines.append(f"- 当前芯片：{chip['name']}（类型：{chip_type}）")
            added = True

        testplan = data.get("recent_testplan") or {}
        if testplan.get("file_name") or testplan.get("summary"):
            summary = testplan.get("summary") or "最近一次 TestPlan 结果已生成"
            lines.append(f"- 最近 TestPlan：{testplan.get('file_name') or '未命名'}，{summary}")
            added = True

        resource_map = data.get("recent_resource_map") or {}
        if resource_map.get("file_name") or resource_map.get("summary"):
            summary = resource_map.get("summary") or "最近一次资源映射已生成"
            lines.append(f"- 最近 ResourceMap：{resource_map.get('file_name') or '未命名'}，{summary}")
            added = True

        codegen = data.get("recent_codegen") or {}
        if codegen.get("template") or codegen.get("summary"):
            summary = codegen.get("summary") or "最近一次代码生成结果可用"
            lines.append(f"- 最近代码模板：{codegen.get('template') or '未记录'}，{summary}")
            added = True

        failure = data.get("recent_failure_topic") or {}
        if failure.get("topic") or failure.get("summary"):
            summary = failure.get("summary") or "最近一次诊断主题已记录"
            label = failure.get("topic") or "最近问题"
            lines.append(f"- 最近关注问题：{label}，{summary}")
            added = True

        notes = data.get("notes") or []
        if notes:
            lines.append(f"- 备注：{notes[0].get('text', '')}")
            added = True

        return "\n".join(lines) if added else ""


_workspace_memory_service: WorkspaceMemoryService | None = None


def get_workspace_memory_service() -> WorkspaceMemoryService:
    global _workspace_memory_service
    if _workspace_memory_service is None:
        _workspace_memory_service = WorkspaceMemoryService()
    return _workspace_memory_service

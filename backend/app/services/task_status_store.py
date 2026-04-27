"""
Persistent task-status store for async module 1 extraction tasks.
Uses one JSON file per task under processed/task_status for restart-safe polling.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import get_settings


class TaskStatusStore:
    """Persist and retrieve async task states."""

    def __init__(self) -> None:
        settings = get_settings()
        self.root = settings.PROCESSED_DIR / "task_status"
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        path = self.root / f"{task_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self.root / f"{task_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def update(self, task_id: str, **changes: Any) -> Dict[str, Any]:
        current = self.get(task_id) or {}
        current.update(changes)
        return self.set(task_id, current)

    def list(self, limit: int = 100) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            payload.setdefault("task_id", path.stem)
            items.append(payload)
        return items

    def delete(self, task_id: str) -> bool:
        path = self.root / f"{task_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    def prune(self, statuses: Optional[set[str]] = None) -> int:
        deleted = 0
        for item in self.list(limit=10000):
            if statuses and item.get("status") not in statuses:
                continue
            if self.delete(item.get("task_id", "")):
                deleted += 1
        return deleted

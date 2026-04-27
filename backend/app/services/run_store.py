"""
Persistent run store for lightweight agent flows.
Phase 1 stores run metadata as JSON files under processed/agent_runs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import get_settings

settings = get_settings()


class RunStore:
    def __init__(self) -> None:
        self.base_dir = settings.PROCESSED_DIR / "agent_runs"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_run(self, run_data: Dict[str, Any]) -> Dict[str, Any]:
        run_id = str(run_data["run_id"])
        path = self.base_dir / f"{run_id}.json"
        path.write_text(json.dumps(run_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return run_data

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self.base_dir / f"{run_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_runs(self, limit: int = 50, flow_name: Optional[str] = None) -> List[Dict[str, Any]]:
        paths = sorted(self.base_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        results: List[Dict[str, Any]] = []
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            if flow_name and data.get("flow_name") != flow_name:
                continue
            results.append(data)
            if len(results) >= limit:
                break
        return results

    def get_artifacts(self, run_id: str) -> List[Dict[str, Any]]:
        data = self.get_run(run_id)
        if not data:
            return []
        return list(data.get("artifacts") or [])


_run_store: Optional[RunStore] = None


def get_run_store() -> RunStore:
    global _run_store
    if _run_store is None:
        _run_store = RunStore()
    return _run_store


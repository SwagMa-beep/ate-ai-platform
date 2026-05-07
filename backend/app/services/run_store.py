"""Persistent run store for lightweight agent flows."""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, is_dataclass
from datetime import datetime
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
        run_dir = self.base_dir / run_id
        artifacts_dir = run_dir / "artifacts"
        run_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        normalized = self._json_safe(dict(run_data))
        normalized_artifacts = self._materialize_artifacts(run_id=run_id, artifacts=normalized.get("artifacts") or [])
        normalized["artifacts"] = normalized_artifacts

        steps = []
        for step in normalized.get("steps") or []:
            item = self._json_safe(dict(step))
            item["artifacts"] = self._materialize_artifacts(run_id=run_id, artifacts=item.get("artifacts") or [])
            steps.append(item)
        normalized["steps"] = steps

        (run_dir / "run.json").write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
        (run_dir / "steps.json").write_text(json.dumps(steps, ensure_ascii=False, indent=2), encoding="utf-8")
        (artifacts_dir / "index.json").write_text(
            json.dumps(normalized_artifacts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return normalized

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        run_dir = self.base_dir / run_id
        run_path = run_dir / "run.json"
        if run_path.exists():
            return json.loads(run_path.read_text(encoding="utf-8"))

        legacy_path = self.base_dir / f"{run_id}.json"
        if legacy_path.exists():
            return json.loads(legacy_path.read_text(encoding="utf-8"))
        return None

    def list_runs(self, limit: int = 50, flow_name: Optional[str] = None) -> List[Dict[str, Any]]:
        paths = sorted(
            list(self.base_dir.glob("*/run.json")) + list(self.base_dir.glob("*.json")),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
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
        run_dir = self.base_dir / run_id
        index_path = run_dir / "artifacts" / "index.json"
        if index_path.exists():
            return json.loads(index_path.read_text(encoding="utf-8"))

        data = self.get_run(run_id)
        if not data:
            return []
        return list(data.get("artifacts") or [])

    def get_artifact(self, run_id: str, artifact_name: str) -> Optional[Dict[str, Any]]:
        artifacts = self.get_artifacts(run_id)
        for artifact in artifacts:
            if artifact.get("name") == artifact_name:
                return artifact
        return None

    def clear_runs(self, flow_name: Optional[str] = None) -> int:
        deleted = 0
        for run in self.list_runs(limit=100000, flow_name=flow_name):
            run_id = str(run.get("run_id") or "").strip()
            if not run_id:
                continue
            deleted += int(self.delete_run(run_id))
        return deleted

    def delete_run(self, run_id: str) -> bool:
        run_dir = self.base_dir / run_id
        if run_dir.exists() and run_dir.is_dir():
            shutil.rmtree(run_dir, ignore_errors=True)
            return True

        legacy_path = self.base_dir / f"{run_id}.json"
        if legacy_path.exists():
            legacy_path.unlink(missing_ok=True)
            return True
        return False

    # ------------------------------------------------------------------
    # Human-in-the-loop: approve / reject
    # ------------------------------------------------------------------

    def approve_run(self, run_id: str, reviewer: str = "") -> Optional[Dict[str, Any]]:
        """Approve a run that is awaiting human review."""
        return self._apply_review_decision(run_id, "approved", reviewer=reviewer)

    def reject_run(
        self,
        run_id: str,
        reviewer: str = "",
        reason: str = "",
        rejection_type: str = "",
        resolution_owner: str = "",
        next_action: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Reject a run that is awaiting human review."""
        return self._apply_review_decision(
            run_id,
            "rejected",
            reviewer=reviewer,
            reason=reason,
            rejection_type=rejection_type,
            resolution_owner=resolution_owner,
            next_action=next_action,
        )

    def _apply_review_decision(
        self,
        run_id: str,
        decision: str,
        *,
        reviewer: str = "",
        reason: str = "",
        rejection_type: str = "",
        resolution_owner: str = "",
        next_action: str = "",
    ) -> Optional[Dict[str, Any]]:
        data = self.get_run(run_id)
        if not data:
            return None

        now = datetime.now().isoformat()
        review_decision = {
            "decision": decision,
            "reviewer": reviewer or "ATE Engineer",
            "reason": reason,
            "reviewed_at": now,
        }
        if rejection_type:
            review_decision["rejection_type"] = rejection_type
        if resolution_owner:
            review_decision["resolution_owner"] = resolution_owner
        if next_action:
            review_decision["next_action"] = next_action
        data["status"] = decision
        data["updated_at"] = now
        data["review_decision"] = review_decision

        return self.save_run(data)

    def update_run_fields(self, run_id: str, **changes: Any) -> Optional[Dict[str, Any]]:
        data = self.get_run(run_id)
        if not data:
            return None
        data.update(changes)
        data["updated_at"] = datetime.now().isoformat()
        return self.save_run(data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _materialize_artifacts(self, *, run_id: str, artifacts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for index, artifact in enumerate(artifacts, start=1):
            item = dict(artifact or {})
            artifact_type = str(item.get("type") or "artifact")
            name = str(item.get("name") or f"{artifact_type}_{index}")
            item["name"] = name
            normalized_item = self._link_artifact_metadata(run_id, item)
            normalized.append(normalized_item)
        return normalized

    def _link_artifact_metadata(self, run_id: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
        item = self._json_safe(dict(artifact))
        metadata_dir = self.base_dir / run_id / "artifacts"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = metadata_dir / f"{item['name']}.json"
        metadata_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        item["metadata_path"] = str(metadata_path)
        return item

    def _json_safe(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._json_safe(item) for item in value]
        if is_dataclass(value):
            return self._json_safe(asdict(value))
        if value.__class__.__name__ == "DataFrame" and hasattr(value, "to_dict"):
            return self._json_safe(value.to_dict(orient="records"))

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return self._json_safe(model_dump())

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return self._json_safe(to_dict())

        tolist = getattr(value, "tolist", None)
        if callable(tolist):
            return self._json_safe(tolist())

        return str(value)


_run_store: Optional[RunStore] = None


def get_run_store() -> RunStore:
    global _run_store
    if _run_store is None:
        _run_store = RunStore()
    return _run_store

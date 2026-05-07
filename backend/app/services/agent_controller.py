"""Lightweight agent controller for orchestrating internal flows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence
from uuid import uuid4


@dataclass
class AgentStepResult:
    agent: str
    status: str
    message: str = ""
    output: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    next_action: Optional[str] = None
    requires_human_review: bool = False


@dataclass
class RunContext:
    run_id: str
    flow_name: str
    input_payload: Dict[str, Any]
    shared: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def state(self) -> Dict[str, Any]:
        """Compatibility alias for flows that prefer `context.state`."""
        return self.shared


class BaseAgent:
    agent_name = "base"

    def run(self, context: RunContext) -> AgentStepResult:
        raise NotImplementedError

    def should_run(self, context: RunContext) -> bool:
        return True

    def max_retries(self) -> int:
        return 0


@dataclass
class AgentRun:
    run_id: str
    flow_name: str
    status: str
    created_at: str
    updated_at: str
    input_payload: Dict[str, Any]
    steps: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    warnings: List[str]
    errors: List[str]
    shared: Dict[str, Any]
    parent_run_id: Optional[str] = None
    continuation_run_id: Optional[str] = None
    triggered_by: Optional[str] = None
    review_source_run_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "flow_name": self.flow_name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "input_payload": self.input_payload,
            "steps": self.steps,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "errors": self.errors,
            "shared": self.shared,
            "parent_run_id": self.parent_run_id,
            "continuation_run_id": self.continuation_run_id,
            "triggered_by": self.triggered_by,
            "review_source_run_id": self.review_source_run_id,
        }


class AgentController:
    """Minimal flow controller for internal agent orchestration."""

    def __init__(self) -> None:
        self._flows: Dict[str, Sequence[BaseAgent]] = {}

    def register_flow(self, flow_name: str, agents: Sequence[BaseAgent]) -> None:
        self._flows[flow_name] = list(agents)

    def get_flow_agent_names(self, flow_name: str) -> List[str]:
        if flow_name not in self._flows:
            raise ValueError(f"Unknown flow: {flow_name}")
        return [agent.agent_name for agent in self._flows[flow_name]]

    def run_flow(
        self,
        *,
        flow_name: str,
        payload: Dict[str, Any],
        initial_shared: Optional[Dict[str, Any]] = None,
        run_id: Optional[str] = None,
        on_update: Optional[Callable[[AgentRun], None]] = None,
    ) -> AgentRun:
        if flow_name not in self._flows:
            raise ValueError(f"Unknown flow: {flow_name}")

        run_id = run_id or f"{flow_name}_{uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()
        context = RunContext(
            run_id=run_id,
            flow_name=flow_name,
            input_payload=dict(payload),
            shared=dict(initial_shared or {}),
        )

        status = "completed"
        updated_at = timestamp
        requires_human_review = False
        if on_update:
            context.shared["progress"] = {
                "phase": "starting",
                "message": "Run created and waiting for the first agent step.",
                "current_agent": None,
                "completed_steps": 0,
                "total_steps": len(self._flows[flow_name]),
            }
            on_update(
                self._build_snapshot(
                    context=context,
                    status="running",
                    created_at=timestamp,
                    updated_at=updated_at,
                )
            )

        for agent in self._flows[flow_name]:
            if not agent.should_run(context):
                updated_at = datetime.now().isoformat()
                skipped_at = datetime.now().isoformat()
                context.steps.append(
                    {
                        "agent": agent.agent_name,
                        "status": "skipped",
                        "message": "Skipped by should_run condition.",
                        "warnings": [],
                        "errors": [],
                        "artifacts": [],
                        "metadata": {
                            "skipped": True,
                            "attempts": 0,
                            "max_retries": agent.max_retries(),
                            "started_at": skipped_at,
                            "finished_at": skipped_at,
                            "duration_seconds": 0.0,
                        },
                        "next_action": None,
                        "requires_human_review": False,
                        "quality": {"score": 1.0, "fallback_used": False, "risk_flags": []},
                    }
                )
                context.shared["progress"] = {
                    "phase": "running",
                    "message": f"{agent.agent_name} was skipped.",
                    "current_agent": agent.agent_name,
                    "completed_steps": len(context.steps),
                    "total_steps": len(self._flows[flow_name]),
                }
                if on_update:
                    on_update(
                        self._build_snapshot(
                            context=context,
                            status="running",
                            created_at=timestamp,
                            updated_at=updated_at,
                        )
                    )
                continue

            step_started_at = datetime.now()
            context.steps.append(
                {
                    "agent": agent.agent_name,
                    "status": "running",
                    "message": f"{agent.agent_name} is running.",
                    "warnings": [],
                    "errors": [],
                    "artifacts": [],
                    "metadata": {
                        "attempts": 0,
                        "max_retries": agent.max_retries(),
                        "started_at": step_started_at.isoformat(),
                    },
                    "next_action": None,
                    "requires_human_review": False,
                    "quality": None,
                }
            )
            context.shared["progress"] = {
                "phase": "running",
                "message": f"{agent.agent_name} is running.",
                "current_agent": agent.agent_name,
                "completed_steps": max(len(context.steps) - 1, 0),
                "total_steps": len(self._flows[flow_name]),
            }
            if on_update:
                on_update(
                    self._build_snapshot(
                        context=context,
                        status="running",
                        created_at=timestamp,
                        updated_at=datetime.now().isoformat(),
                    )
                )

            step_result = self._execute_agent_with_retries(agent, context)
            updated_at = datetime.now().isoformat()
            duration_seconds = round((datetime.now() - step_started_at).total_seconds(), 2)
            context.shared.update(step_result.output or {})
            normalized_artifacts = self._normalize_artifacts(
                run_id=run_id,
                agent_name=step_result.agent,
                artifacts=step_result.artifacts or [],
            )
            context.artifacts.extend(normalized_artifacts)
            context.warnings.extend(step_result.warnings or [])
            context.errors.extend(step_result.errors or [])
            requires_human_review = requires_human_review or step_result.requires_human_review

            context.steps[-1] = (
                {
                    "agent": step_result.agent,
                    "status": step_result.status,
                    "message": step_result.message,
                    "warnings": step_result.warnings,
                    "errors": step_result.errors,
                    "artifacts": normalized_artifacts,
                    "metadata": {
                        **(step_result.metadata or {}),
                        "started_at": context.steps[-1].get("metadata", {}).get("started_at"),
                        "finished_at": updated_at,
                        "duration_seconds": duration_seconds,
                    },
                    "next_action": step_result.next_action,
                    "requires_human_review": step_result.requires_human_review,
                    "quality": self._compute_step_quality(step_result),
                }
            )
            context.shared["progress"] = {
                "phase": "running" if step_result.status not in {"failed", "human_review_required"} else step_result.status,
                "message": step_result.message or f"{step_result.agent} finished.",
                "current_agent": step_result.agent,
                "completed_steps": len(context.steps),
                "total_steps": len(self._flows[flow_name]),
            }
            if step_result.status in {"failed", "human_review_required"}:
                status = step_result.status
                if on_update:
                    on_update(
                        self._build_snapshot(
                            context=context,
                            status=status,
                            created_at=timestamp,
                            updated_at=updated_at,
                        )
                    )
                break
            if step_result.status == "warning":
                status = "warning"
            if on_update:
                on_update(
                    self._build_snapshot(
                        context=context,
                        status="running",
                        created_at=timestamp,
                        updated_at=updated_at,
                    )
                )

        if status in {"completed", "warning"} and requires_human_review:
            status = "human_review_required"

        context.shared["progress"] = {
            "phase": status,
            "message": f"{flow_name} finished with status {status}.",
            "current_agent": context.steps[-1]["agent"] if context.steps else None,
            "completed_steps": len(context.steps),
            "total_steps": len(self._flows[flow_name]),
        }

        final_run = self._build_snapshot(
            context=context,
            status=status,
            created_at=timestamp,
            updated_at=updated_at,
        )
        if on_update:
            on_update(final_run)
        return final_run

    def _execute_agent_with_retries(self, agent: BaseAgent, context: RunContext) -> AgentStepResult:
        max_retries = max(0, int(agent.max_retries()))
        attempt = 0
        final_result: Optional[AgentStepResult] = None

        while attempt <= max_retries:
            attempt += 1
            try:
                step_result = agent.run(context)
            except Exception as exc:  # pragma: no cover - defensive
                step_result = AgentStepResult(
                    agent=agent.agent_name,
                    status="failed",
                    message=f"{agent.agent_name} raised an unexpected exception.",
                    errors=[str(exc)],
                    metadata={"exception_type": exc.__class__.__name__},
                )

            final_result = step_result
            if step_result.status != "failed" or attempt > max_retries:
                break

        assert final_result is not None  # for type-checkers
        final_result.metadata = {
            **(final_result.metadata or {}),
            "attempts": attempt,
            "max_retries": max_retries,
            "retries_used": max(0, attempt - 1),
        }
        return final_result

    @staticmethod
    def _compute_step_quality(result: AgentStepResult) -> Dict[str, Any]:
        risk_flags: List[str] = []
        fallback_used = bool(result.metadata.get("fallback_used"))

        if result.status == "failed":
            score = 0.0
            risk_flags.append(f"{result.agent} 执行失败")
        elif result.status == "human_review_required":
            score = 0.4
            risk_flags.append("需要人工复核")
        elif result.status == "warning" or result.warnings:
            score = 0.7
            if result.warnings:
                risk_flags.append(f"存在 {len(result.warnings)} 个警告")
        else:
            score = 1.0

        # Penalise for errors / warnings
        error_penalty = min(len(result.errors or []) * 0.12, 0.6)
        warning_penalty = min(len(result.warnings or []) * 0.06, 0.3)
        score = max(0.0, round(score - error_penalty - warning_penalty, 2))

        if fallback_used:
            risk_flags.append("使用了降级策略")

        return {
            "score": score,
            "fallback_used": fallback_used,
            "risk_flags": risk_flags,
        }

    @staticmethod
    def _normalize_artifacts(
        *,
        run_id: str,
        agent_name: str,
        artifacts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        timestamp = datetime.now().isoformat()
        normalized: List[Dict[str, Any]] = []
        for index, artifact in enumerate(artifacts, start=1):
            item = dict(artifact or {})
            artifact_type = str(item.get("type") or "artifact")
            item.setdefault("name", f"{artifact_type}_{index}")
            item.setdefault("producer", agent_name)
            item.setdefault("run_id", run_id)
            item.setdefault("created_at", timestamp)
            normalized.append(item)
        return normalized

    @staticmethod
    def _build_snapshot(
        *,
        context: RunContext,
        status: str,
        created_at: str,
        updated_at: str,
    ) -> AgentRun:
        return AgentRun(
            run_id=context.run_id,
            flow_name=context.flow_name,
            status=status,
            created_at=created_at,
            updated_at=updated_at,
            input_payload=dict(context.input_payload),
            steps=[dict(step) for step in context.steps],
            artifacts=[dict(artifact) for artifact in context.artifacts],
            warnings=list(dict.fromkeys(context.warnings)),
            errors=list(dict.fromkeys(context.errors)),
            shared=dict(context.shared),
        )

"""
Lightweight agent controller for orchestrating internal flows.
Phase 1 focuses on module 3 code generation without breaking existing APIs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import uuid4


@dataclass
class AgentStepResult:
    agent: str
    status: str
    output: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


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


class BaseAgent:
    agent_name = "base"

    def run(self, context: RunContext) -> AgentStepResult:
        raise NotImplementedError


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
        }


class AgentController:
    """Minimal flow controller for internal agent orchestration."""

    def __init__(self) -> None:
        self._flows: Dict[str, Sequence[BaseAgent]] = {}

    def register_flow(self, flow_name: str, agents: Sequence[BaseAgent]) -> None:
        self._flows[flow_name] = list(agents)

    def run_flow(
        self,
        *,
        flow_name: str,
        payload: Dict[str, Any],
        initial_shared: Optional[Dict[str, Any]] = None,
    ) -> AgentRun:
        if flow_name not in self._flows:
            raise ValueError(f"Unknown flow: {flow_name}")

        run_id = f"{flow_name}_{uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()
        context = RunContext(
            run_id=run_id,
            flow_name=flow_name,
            input_payload=dict(payload),
            shared=dict(initial_shared or {}),
        )

        status = "completed"
        updated_at = timestamp

        for agent in self._flows[flow_name]:
            step_result = agent.run(context)
            updated_at = datetime.now().isoformat()
            context.shared.update(step_result.output or {})
            context.artifacts.extend(step_result.artifacts or [])
            context.warnings.extend(step_result.warnings or [])
            context.errors.extend(step_result.errors or [])
            context.steps.append(
                {
                    "agent": step_result.agent,
                    "status": step_result.status,
                    "warnings": step_result.warnings,
                    "errors": step_result.errors,
                    "artifacts": step_result.artifacts,
                    "metadata": step_result.metadata,
                }
            )
            if step_result.status != "completed":
                status = step_result.status
                break

        return AgentRun(
            run_id=run_id,
            flow_name=flow_name,
            status=status,
            created_at=timestamp,
            updated_at=updated_at,
            input_payload=context.input_payload,
            steps=context.steps,
            artifacts=context.artifacts,
            warnings=list(dict.fromkeys(context.warnings)),
            errors=list(dict.fromkeys(context.errors)),
            shared=context.shared,
        )


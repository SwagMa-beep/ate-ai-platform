"""Post-review revision routing flow for rejected runs."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent, RunContext


def _resolution_owner(rejection_type: str) -> str:
    if rejection_type == "auto_fixable":
        return "agent"
    return "user"


def _recommended_next_action(rejection_type: str) -> str:
    if rejection_type == "input_issue":
        return "Replace the source datasheet or provide missing input context, then create a new run."
    if rejection_type == "engineering_decision":
        return "Provide an explicit engineering decision or bench constraint, then rerun the flow."
    return "Prepare an agent revision run using the rejection reason, diagnostics, and current artifacts."


class RevisionRequestBuilderAgent(BaseAgent):
    agent_name = "revision_request_builder"

    def run(self, context: RunContext) -> AgentStepResult:
        source_run = context.input_payload["source_run"]
        rejection_type = context.input_payload.get("rejection_type") or "engineering_decision"
        reviewer = context.input_payload.get("reviewer") or "ATE Engineer"
        reason = context.input_payload.get("reason") or "Engineer requested changes before continuing."
        review = dict((source_run.get("shared") or {}).get("review") or {})
        owner = _resolution_owner(rejection_type)
        next_action = _recommended_next_action(rejection_type)
        must_review_items = list(review.get("must_review_items") or [])
        recommendations = list(review.get("recommendations") or [])
        evidence = {
            "source_run_id": source_run["run_id"],
            "source_flow_name": source_run.get("flow_name"),
            "rejection_type": rejection_type,
            "reviewer": reviewer,
            "reason": reason,
            "resolution_owner": owner,
            "risk_level": review.get("risk_level", "unknown"),
            "must_review_item_count": len(must_review_items),
            "artifact_count": len(source_run.get("artifacts") or []),
            "error_count": len(source_run.get("errors") or []),
            "warning_count": len(source_run.get("warnings") or []),
            "next_action": next_action,
            "updated_at": datetime.now().isoformat(),
        }
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Revision request was prepared from the rejection decision.",
            output={
                "revision_request": evidence,
                "revision_supporting_context": {
                    "must_review_items": must_review_items,
                    "recommendations": recommendations,
                },
            },
            artifacts=[
                {
                    "name": "revision_request",
                    "type": "revision_request",
                    "summary": evidence,
                }
            ],
            next_action=next_action,
        )


class RevisionDispatchPlannerAgent(BaseAgent):
    agent_name = "revision_dispatch_planner"

    def run(self, context: RunContext) -> AgentStepResult:
        request = dict(context.shared.get("revision_request") or {})
        owner = request.get("resolution_owner", "user")
        rejection_type = request.get("rejection_type", "engineering_decision")
        dispatch_items: List[str]
        if owner == "agent":
            dispatch_items = [
                "Use the rejection reason as the revision objective.",
                "Reuse the source run artifacts and diagnostics as evidence.",
                "Regenerate the affected outputs before asking for review again.",
            ]
        else:
            dispatch_items = [
                "Ask the engineer to adjust the datasheet, scope, or constraints.",
                "Capture the updated decision in the next run payload.",
                "Start a fresh run after the missing information is supplied.",
            ]
        dispatch = {
            "rejection_type": rejection_type,
            "resolution_owner": owner,
            "dispatch_items": dispatch_items,
            "ready_for_agent_revision": owner == "agent",
        }
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Revision routing plan was prepared.",
            output={"revision_dispatch": dispatch},
            artifacts=[
                {
                    "name": "revision_dispatch",
                    "type": "revision_dispatch",
                    "summary": dispatch,
                }
            ],
        )


def build_post_review_revision_controller() -> AgentController:
    controller = AgentController()
    controller.register_flow(
        "post_review_revision",
        [
            RevisionRequestBuilderAgent(),
            RevisionDispatchPlannerAgent(),
        ],
    )
    return controller

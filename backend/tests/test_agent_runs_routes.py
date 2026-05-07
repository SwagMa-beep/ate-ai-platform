import time

from fastapi.testclient import TestClient

from app.api.v1 import agent_runs as agent_runs_module
from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent, RunContext
from app.main import app
from app.services.run_store import get_run_store


def test_agent_run_routes_are_mounted():
    paths = {route.path for route in app.routes}
    assert "/api/v1/agent-runs" in paths
    assert "/api/v1/agent-runs/{run_id}" in paths
    assert "/api/v1/agent-runs/{run_id}/artifacts" in paths
    assert "/api/v1/agent-runs/{run_id}/artifacts/{artifact_name}" in paths


def test_approve_agent_run_creates_continuation_run(tmp_path):
    client = TestClient(app)
    run_store = get_run_store()
    run_store.base_dir = tmp_path / "agent_runs"
    run_store.base_dir.mkdir(parents=True, exist_ok=True)

    source_run = {
        "run_id": "full_ate_development_approve01",
        "flow_name": "full_ate_development",
        "status": "human_review_required",
        "created_at": "2026-04-28T18:00:00",
        "updated_at": "2026-04-28T18:00:00",
        "input_payload": {
            "file_id": "abc12345",
            "chip_name": "DemoChip",
            "chip_type": "digital",
        },
        "steps": [],
        "artifacts": [
            {
                "name": "review_summary",
                "type": "review_summary",
                "summary": {"risk_level": "medium"},
            }
        ],
        "warnings": [],
        "errors": [],
        "shared": {
            "review": {
                "risk_level": "medium",
                "must_review_items": ["Check compile diagnostics"],
                "recommendations": ["Export final package before bench usage"],
            },
            "generated_result": {
                "chip_name": "DemoChip",
                "chip_type": "digital",
                "package_export": {"generation_id": "pkg001"},
            },
        },
    }
    run_store.save_run(source_run)

    response = client.post(
        "/api/v1/agent-runs/full_ate_development_approve01/approve",
        json={"reviewer": "QA Reviewer"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "approved"
    assert payload["review_decision"]["reviewer"] == "QA Reviewer"
    assert payload["continuation_run_id"].startswith("post_review_delivery_")
    assert payload["continuation_run"]["parent_run_id"] == "full_ate_development_approve01"
    assert payload["continuation_run"]["review_source_run_id"] == "full_ate_development_approve01"
    assert payload["continuation_run"]["triggered_by"] == "approval"
    assert payload["continuation_run"]["artifacts"][0]["type"] == "delivery_summary"
    assert payload["continuation_run"]["artifacts"][0]["summary"]["approved_by"] == "QA Reviewer"
    assert payload["continuation_run"]["artifacts"][1]["summary"]["checklist_item_count"] == 5
    assert payload["continuation_run"]["artifacts"][2]["summary"]["generation_id"] == "pkg001"
    assert payload["continuation_run"]["shared"]["delivery_package"]["linked_artifacts"]["review_summary"] is True

    persisted_parent = run_store.get_run("full_ate_development_approve01")
    assert persisted_parent["continuation_run_id"] == payload["continuation_run_id"]

    persisted_child = run_store.get_run(payload["continuation_run_id"])
    assert persisted_child is not None
    assert persisted_child["flow_name"] == "post_review_delivery"


def test_reject_agent_run_creates_revision_flow(tmp_path):
    client = TestClient(app)
    run_store = get_run_store()
    run_store.base_dir = tmp_path / "agent_runs"
    run_store.base_dir.mkdir(parents=True, exist_ok=True)

    source_run = {
        "run_id": "full_ate_development_reject01",
        "flow_name": "full_ate_development",
        "status": "human_review_required",
        "created_at": "2026-04-28T18:00:00",
        "updated_at": "2026-04-28T18:00:00",
        "input_payload": {
            "file_id": "abc12345",
            "chip_name": "DemoChip",
            "chip_type": "digital",
        },
        "steps": [],
        "artifacts": [
            {
                "name": "review_summary",
                "type": "review_summary",
                "summary": {"risk_level": "high"},
            }
        ],
        "warnings": ["Need bench confirmation"],
        "errors": [],
        "shared": {
            "review": {
                "risk_level": "high",
                "must_review_items": ["Confirm pin resource allocation"],
                "recommendations": ["Provide clearer bench limits before continuing"],
            },
        },
    }
    run_store.save_run(source_run)

    response = client.post(
        "/api/v1/agent-runs/full_ate_development_reject01/reject",
        json={
            "reviewer": "QA Reviewer",
            "reason": "Bench constraints are still unclear.",
            "rejection_type": "engineering_decision",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "rejected"
    assert payload["review_decision"]["reviewer"] == "QA Reviewer"
    assert payload["review_decision"]["rejection_type"] == "engineering_decision"
    assert payload["review_decision"]["resolution_owner"] == "user"
    assert payload["continuation_run_id"].startswith("post_review_revision_")
    assert payload["continuation_run"]["flow_name"] == "post_review_revision"
    assert payload["continuation_run"]["parent_run_id"] == "full_ate_development_reject01"
    assert payload["continuation_run"]["review_source_run_id"] == "full_ate_development_reject01"
    assert payload["continuation_run"]["artifacts"][0]["type"] == "revision_request"
    assert payload["continuation_run"]["artifacts"][1]["type"] == "revision_dispatch"
    assert payload["continuation_run"]["shared"]["revision_dispatch"]["ready_for_agent_revision"] is False

    persisted_parent = run_store.get_run("full_ate_development_reject01")
    assert persisted_parent["continuation_run_id"] == payload["continuation_run_id"]

    persisted_child = run_store.get_run(payload["continuation_run_id"])
    assert persisted_child is not None
    assert persisted_child["flow_name"] == "post_review_revision"


def test_reject_auto_fixable_run_starts_agent_revision(tmp_path):
    client = TestClient(app)
    run_store = get_run_store()
    run_store.base_dir = tmp_path / "agent_runs"
    run_store.base_dir.mkdir(parents=True, exist_ok=True)

    source_run = {
        "run_id": "full_ate_development_reject02",
        "flow_name": "full_ate_development",
        "status": "human_review_required",
        "created_at": "2026-04-28T18:00:00",
        "updated_at": "2026-04-28T18:00:00",
        "input_payload": {
            "goal": "Generate ATE package",
            "file_id": "missing-file",
            "chip_name": "DemoChip",
            "chip_type": "digital",
            "export_package": False,
        },
        "steps": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "shared": {
            "review": {
                "risk_level": "medium",
                "must_review_items": ["Fix compile diagnostics"],
                "recommendations": ["Regenerate code after fixing the compile issue"],
            },
        },
    }
    run_store.save_run(source_run)

    response = client.post(
        "/api/v1/agent-runs/full_ate_development_reject02/reject",
        json={
            "reviewer": "QA Reviewer",
            "reason": "Compile diagnostics can be repaired automatically.",
            "rejection_type": "auto_fixable",
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "rejected"
    assert payload["review_decision"]["rejection_type"] == "auto_fixable"
    assert payload["review_decision"]["resolution_owner"] == "agent"
    assert payload["continuation_run"]["flow_name"] == "full_ate_development"
    assert payload["continuation_run"]["status"] == "running"
    assert payload["continuation_run"]["parent_run_id"] == payload["routing_run"]["run_id"]
    assert payload["routing_run"]["flow_name"] == "post_review_revision"
    assert payload["routing_run"]["continuation_run_id"] == payload["continuation_run"]["run_id"]

    persisted_parent = run_store.get_run("full_ate_development_reject02")
    assert persisted_parent["continuation_run_id"] == payload["continuation_run"]["run_id"]


class _SlowSuccessAgent(BaseAgent):
    agent_name = "input_resolver"

    def run(self, context: RunContext) -> AgentStepResult:
        time.sleep(0.15)
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Input resolved for async integration test.",
            output={
                "generated_result": {
                    "chip_name": "DemoChip",
                    "chip_type": "digital",
                    "compile_validation": {"passed": True},
                    "static_analysis": {"passed": True},
                    "package_export": {"generation_id": "pkg-async-001"},
                }
            },
            artifacts=[{"type": "source_pdf", "summary": {"file_id": context.input_payload.get("file_id")}}],
        )


class _SlowReviewAgent(BaseAgent):
    agent_name = "review_agent"

    def run(self, context: RunContext) -> AgentStepResult:
        time.sleep(0.15)
        review = {
            "overall_status": "needs_human_review",
            "risk_level": "medium",
            "must_review_items": ["Check compile validation before bench usage"],
            "recommendations": ["Approve only after reviewing generated artifacts"],
        }
        return AgentStepResult(
            agent=self.agent_name,
            status="warning",
            message="Async test flow reached review.",
            output={"review": review},
            warnings=review["must_review_items"],
            artifacts=[{"type": "review_summary", "summary": {"risk_level": "medium"}}],
            requires_human_review=True,
            next_action="Review the artifacts before approval.",
        )


def test_async_full_run_is_visible_immediately_and_can_be_approved(tmp_path, monkeypatch):
    client = TestClient(app)
    run_store = get_run_store()
    run_store.base_dir = tmp_path / "agent_runs"
    run_store.base_dir.mkdir(parents=True, exist_ok=True)

    controller = AgentController()
    controller.register_flow("full_ate_development", [_SlowSuccessAgent(), _SlowReviewAgent()])
    monkeypatch.setattr(agent_runs_module, "full_flow_controller", controller)

    response = client.post(
        "/api/v1/agent-runs",
        json={
            "flow_name": "full_ate_development",
            "goal": "Generate a reviewable ATE package",
            "file_id": "async-file-001",
            "async_mode": True,
        },
    )

    assert response.status_code == 202
    payload = response.json()["data"]
    run_id = payload["run_id"]
    assert payload["status"] == "running"
    assert payload["shared"]["progress"]["phase"] == "queued"

    visible_run = client.get(f"/api/v1/agent-runs/{run_id}")
    assert visible_run.status_code == 200
    visible_data = visible_run.json()["data"]
    assert visible_data["run_id"] == run_id
    assert visible_data["status"] == "running"

    terminal_data = None
    for _ in range(30):
        poll = client.get(f"/api/v1/agent-runs/{run_id}")
        assert poll.status_code == 200
        terminal_data = poll.json()["data"]
        if terminal_data["status"] == "human_review_required":
            break
        time.sleep(0.05)

    assert terminal_data is not None
    assert terminal_data["status"] == "human_review_required"
    assert terminal_data["steps"][-1]["agent"] == "review_agent"
    assert terminal_data["shared"]["progress"]["phase"] == "human_review_required"

    approve = client.post(f"/api/v1/agent-runs/{run_id}/approve", json={"reviewer": "Integration Reviewer"})
    assert approve.status_code == 200
    approved_data = approve.json()["data"]
    assert approved_data["status"] == "approved"
    assert approved_data["continuation_run"]["flow_name"] == "post_review_delivery"
    assert approved_data["continuation_run"]["parent_run_id"] == run_id

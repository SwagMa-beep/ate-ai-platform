"""Post-review delivery flow for approved agent runs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from app.services.agent_controller import AgentController, AgentStepResult, BaseAgent, RunContext


class ApprovedArtifactFinalizerAgent(BaseAgent):
    agent_name = "approved_artifact_finalizer"

    def run(self, context: RunContext) -> AgentStepResult:
        source_run = context.input_payload["source_run"]
        reviewer = context.input_payload.get("approved_by") or "ATE Engineer"
        approved_at = context.input_payload.get("approved_at") or datetime.now().isoformat()
        source_artifacts = list(source_run.get("artifacts") or [])
        source_shared = dict(source_run.get("shared") or {})
        generated_result = dict(source_shared.get("generated_result") or {})
        review = dict(source_shared.get("review") or {})
        package_export = dict(generated_result.get("package_export") or {})
        static_analysis = dict(generated_result.get("static_analysis") or {})
        compile_validation = dict(generated_result.get("compile_validation") or {})
        chip_name = (
            generated_result.get("chip_name")
            or source_shared.get("extraction_result", {}).get("chip_name")
            or source_run.get("input_payload", {}).get("chip_name")
            or "UnknownChip"
        )
        chip_type = (
            generated_result.get("chip_type")
            or source_shared.get("extraction_result", {}).get("chip_type")
            or source_run.get("input_payload", {}).get("chip_type")
            or "UNKNOWN"
        )
        file_id = source_run.get("input_payload", {}).get("file_id")
        must_review_items = list(review.get("must_review_items") or [])
        recommendations = list(review.get("recommendations") or [])
        package_ready = bool(package_export)
        selected_test_items = list(generated_result.get("test_items") or [])
        checklist_items = [
            {
                "id": "compile-precheck",
                "label": "Compile precheck reviewed",
                "done": bool(compile_validation.get("passed")),
                "detail": "Confirm compile diagnostics were reviewed and accepted by the engineer.",
            },
            {
                "id": "resource-map",
                "label": "Resource mapping verified",
                "done": any(item.get("type") == "resource_mapping" for item in source_artifacts),
                "detail": "Confirm adapter mapping, power pins and PGS bindings match the target bench setup.",
            },
            {
                "id": "vector-pgs",
                "label": "Vector / PGS dependencies checked",
                "done": not any("VECDIO" in item or "PGS" in item for item in must_review_items),
                "detail": "Verify VECDIO labels, time sets and PGS / AutoLoad settings before bench usage.",
            },
            {
                "id": "power-pins",
                "label": "Power and ground pins confirmed",
                "done": True,
                "detail": "Cross-check DUT power and ground definitions against the extracted pin list.",
            },
            {
                "id": "test-coverage",
                "label": "Selected test items reviewed",
                "done": bool(selected_test_items),
                "detail": "Review selected test items and ensure critical coverage matches the engineering goal.",
            },
        ]
        ready_for_bench = all(item["done"] for item in checklist_items[:3]) and package_ready
        delivery_summary = {
            "source_run_id": source_run["run_id"],
            "chip_name": chip_name,
            "chip_type": chip_type,
            "file_id": file_id,
            "approved_by": reviewer,
            "approved_at": approved_at,
            "package_ready": package_ready,
            "ready_for_bench": ready_for_bench,
            "risk_level": review.get("risk_level", "unknown"),
            "artifact_count": len(source_artifacts),
            "must_review_count": len(must_review_items),
            "selected_test_item_count": len(selected_test_items),
            "static_checks_passed": bool(static_analysis.get("passed", False)),
            "compile_checks_passed": bool(compile_validation.get("passed", False)),
            "recommended_next_step": "Proceed with bench preparation and final engineer checks.",
        }
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Approved artifacts were finalized for delivery.",
            output={
                "delivery_summary": delivery_summary,
                "bench_checklist": {
                    "must_review_items": must_review_items,
                    "recommendations": recommendations,
                    "package_ready": package_ready,
                    "ready_for_bench": ready_for_bench,
                    "items": checklist_items,
                },
                "source_run_summary": {
                    "run_id": source_run["run_id"],
                    "flow_name": source_run.get("flow_name"),
                    "status": source_run.get("status"),
                },
            },
            artifacts=[
                {
                    "name": "delivery_summary",
                    "type": "delivery_summary",
                    "summary": delivery_summary,
                },
                {
                    "name": "bench_checklist",
                    "type": "bench_checklist",
                    "summary": {
                        "ready_for_bench": ready_for_bench,
                        "must_review_count": len(must_review_items),
                        "recommendation_count": len(recommendations),
                        "package_ready": package_ready,
                        "checklist_item_count": len(checklist_items),
                    },
                },
            ],
            metadata={"approved_by": reviewer},
            next_action="Open the delivery summary and complete the bench checklist.",
        )


class DeliveryPackagerAgent(BaseAgent):
    agent_name = "delivery_packager"

    def run(self, context: RunContext) -> AgentStepResult:
        summary = dict(context.shared.get("delivery_summary") or {})
        checklist = dict(context.shared.get("bench_checklist") or {})
        package_ready = bool(checklist.get("package_ready"))
        source_run = context.input_payload["source_run"]
        source_shared = dict(source_run.get("shared") or {})
        generated_result = dict(source_shared.get("generated_result") or {})
        package_export = dict(generated_result.get("package_export") or {})
        final_package = {
            "ready_for_bench": bool(checklist.get("ready_for_bench")),
            "package_ready": package_ready,
            "source_run_id": summary.get("source_run_id"),
            "chip_name": summary.get("chip_name"),
            "chip_type": summary.get("chip_type"),
            "generation_id": package_export.get("generation_id"),
            "download_url": package_export.get("download_url"),
            "output_dir": package_export.get("output_dir"),
            "generated_file_count": len(package_export.get("generated_files") or []),
            "linked_artifacts": {
                "review_summary": any(item.get("type") == "review_summary" for item in source_run.get("artifacts") or []),
                "compile_validation": bool(generated_result.get("compile_validation")),
                "static_analysis": bool(generated_result.get("static_analysis")),
                "engineering_package": any(item.get("type") == "engineering_package" for item in source_run.get("artifacts") or []),
            },
        }
        return AgentStepResult(
            agent=self.agent_name,
            status="completed",
            message="Delivery package summary prepared.",
            output={"delivery_package": final_package},
            artifacts=[
                {
                    "name": "final_package",
                    "type": "final_package",
                    "summary": final_package,
                }
            ],
        )


def build_post_review_delivery_controller() -> AgentController:
    controller = AgentController()
    controller.register_flow(
        "post_review_delivery",
        [
            ApprovedArtifactFinalizerAgent(),
            DeliveryPackagerAgent(),
        ],
    )
    return controller

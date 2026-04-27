from pathlib import Path

from app.flows.module1_extract_flow import build_module1_extract_controller, finalize_module1_run
from app.models.testplan import ExtractionResult, PinDefinition
from app.services.testplan_service import TestPlanService


def test_module1_agent_controller_completes_extract_flow(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_extract_from_pdf(self, pdf_path: str, pages=None, max_workers=3, progress_callback=None):
        return ExtractionResult(
            status="success",
            chip_name="HD74LS00P",
            chip_type="DIGITAL_74",
            test_scenario="DIGITAL",
            total_params=12,
            a_params=4,
            b_params=4,
            c_params=4,
            blocked_params=0,
            dc_test_items=8,
            ac_test_items=4,
            ldo_test_items=0,
            warnings=["check vector labels"],
            sts_compatibility={"is_compatible": True},
            pin_definitions=[
                PinDefinition(pin_no=1, pin_name="A1", direction="IN"),
                PinDefinition(pin_no=2, pin_name="Y1", direction="OUT"),
            ],
            range_recommendations=[],
        )

    monkeypatch.setattr(TestPlanService, "extract_from_pdf", fake_extract_from_pdf)

    service = TestPlanService()
    controller = build_module1_extract_controller(service=service)
    run = controller.run_flow(
        flow_name="module1_extract",
        payload={
            "file_id": "abc12345",
            "pdf_path": str(pdf_path),
            "pages": "1-3",
            "max_workers": 2,
        },
    )

    data = finalize_module1_run(run, "abc12345")
    assert run.status == "completed"
    assert data["chip_name"] == "HD74LS00P"
    assert data["statistics"]["total"] == 12
    assert data["pin_count"] == 2
    assert data["run"]["steps"][0]["agent"] == "input_resolver"
    assert data["run"]["steps"][1]["agent"] == "testplan_extractor"


def test_module1_agent_controller_stops_on_extract_failure(monkeypatch, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_extract_from_pdf(self, pdf_path: str, pages=None, max_workers=3, progress_callback=None):
        return ExtractionResult(status="error", errors=["LLM unavailable"])

    monkeypatch.setattr(TestPlanService, "extract_from_pdf", fake_extract_from_pdf)

    service = TestPlanService()
    controller = build_module1_extract_controller(service=service)
    run = controller.run_flow(
        flow_name="module1_extract",
        payload={
            "file_id": "abc12345",
            "pdf_path": str(pdf_path),
            "pages": None,
            "max_workers": 2,
        },
    )

    assert run.status == "failed"
    assert run.errors == ["LLM unavailable"]
    assert run.steps[-1]["metadata"]["failure_kind"] == "extraction_failed"

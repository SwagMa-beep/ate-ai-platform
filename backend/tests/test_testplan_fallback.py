from pathlib import Path

from app.models.testplan import DCParam, PinDefinition
from app.services.testplan_service import TestPlanService
import app.services.testplan_service as testplan_service_module


def test_extract_retries_full_context_when_filtered_pages_return_no_params(monkeypatch, tmp_path):
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 demo")

    chunks = [
        {"page": "1", "content": "Cover page only"},
        {"page": "2", "content": "Electrical Characteristics\nVIH VIL VOH VOL"},
        {"page": "3", "content": "Pin Arrangement\n1 VCC\n2 GND"},
    ]

    class _FakeParser:
        def __init__(self, pdf_path: str):
            self.pdf_path = pdf_path

        def parse(self, pages=None):
            return chunks

    class _ValidationSummary:
        errors = []
        warnings = []
        sts_warnings = []

    monkeypatch.setattr(testplan_service_module, "PDFParser", _FakeParser)
    monkeypatch.setattr(testplan_service_module, "export_excel", lambda *args, **kwargs: None)
    monkeypatch.setattr(testplan_service_module.settings, "PROCESSED_DIR", tmp_path)
    monkeypatch.setattr(TestPlanService, "_build_cache_key", lambda self, pdf_path_obj, pages: "fallback-test")
    monkeypatch.setattr(TestPlanService, "_load_cached_result", lambda self, **kwargs: None)
    monkeypatch.setattr(TestPlanService, "_save_cached_result", lambda self, *args, **kwargs: None)
    monkeypatch.setattr(TestPlanService, "_filter_and_batch_chunks", staticmethod(lambda raw_chunks: [raw_chunks[0]]))
    monkeypatch.setattr(TestPlanService, "_extract_local_params_from_chunks", staticmethod(lambda llm_chunks, chip_type: []))
    monkeypatch.setattr(TestPlanService, "_extract_pin_definitions_from_chunks", staticmethod(lambda llm_chunks: []))
    monkeypatch.setattr(TestPlanService, "_drop_local_pin_chunks", staticmethod(lambda llm_chunks, local_pins: llm_chunks))
    monkeypatch.setattr(TestPlanService, "_print_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(TestPlanService, "_print_chip_type_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(TestPlanService, "_print_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(TestPlanService, "_generate_range_recommendations", lambda self, df, chip_type: [])

    service = TestPlanService()
    monkeypatch.setattr(service.llm_extractor, "detect_chip_type", lambda chunks: "UNKNOWN")

    extract_calls = []

    def fake_extract_parallel(llm_chunks, chip_type, max_workers, progress_callback=None):
        extract_calls.append([chunk["page"] for chunk in llm_chunks])
        if len(extract_calls) == 1:
            return [], []
        return (
            [
                DCParam(
                    param_name="VIH",
                    category="A",
                    test_scenario="GENERAL",
                    min_val=2.0,
                    unit="V",
                )
            ],
            [PinDefinition(pin_no=1, pin_name="VCC", direction="PWR")],
        )

    monkeypatch.setattr(service.llm_extractor, "extract_parallel", fake_extract_parallel)
    monkeypatch.setattr(
        service.validator,
        "clean_and_validate",
        lambda df, chip_type: df.assign(Status="待复核", Validation_Error="", STS_Warning=""),
    )
    monkeypatch.setattr(
        service.validator,
        "get_sts_compatibility_report",
        lambda df, chip_type: {
            "chip_type": chip_type,
            "is_compatible": True,
            "issues": [],
            "recommendations": [],
        },
    )
    monkeypatch.setattr(service.validator, "get_validation_summary", lambda df: _ValidationSummary())

    result = service.extract_from_pdf(str(pdf_path))

    assert result.status == "success"
    assert result.total_params == 1
    assert result.pin_definitions[0].pin_name == "VCC"
    assert extract_calls == [["1"], ["1", "2", "3"]]


def test_extract_rejects_sts_manual_with_explicit_message(monkeypatch, tmp_path):
    pdf_path = tmp_path / "manual.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 demo")

    manual_chunks = [
        {"page": "1", "content": "STS8200S 使用指南\n目录\n测试前准备"},
        {"page": "2", "content": "工程新建\n工作站 A\nTestUI\n模板新建工程"},
    ]

    class _FakeParser:
        def __init__(self, pdf_path: str):
            self.pdf_path = pdf_path

        def parse(self, pages=None):
            return manual_chunks

    monkeypatch.setattr(testplan_service_module, "PDFParser", _FakeParser)
    monkeypatch.setattr(TestPlanService, "_load_cached_result", lambda self, **kwargs: None)

    result = TestPlanService().extract_from_pdf(str(pdf_path))

    assert result.status == "error"
    assert result.errors
    assert "使用指南" in result.errors[0]

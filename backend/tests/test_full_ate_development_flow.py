from pathlib import Path

from app.flows.full_ate_development_flow import build_full_ate_development_controller


class _FakeExtractResult:
    status = "success"
    chip_name = "HD74LS00P"
    chip_type = "digital"
    total_params = 6
    warnings = []
    errors = []
    pin_definitions = [
        {"pin_no": 1, "pin_name": "A1", "direction": "IN"},
        {"pin_no": 2, "pin_name": "B1", "direction": "IN"},
        {"pin_no": 3, "pin_name": "Y1", "direction": "OUT"},
        {"pin_no": 7, "pin_name": "GND", "direction": "GND"},
        {"pin_no": 14, "pin_name": "VCC", "direction": "PWR"},
    ]

    def model_dump(self):
        return {
            "status": "success",
            "chip_name": "HD74LS00P",
            "chip_type": "digital",
            "test_scenario": "DIGITAL",
            "total_params": 6,
            "a_params": 2,
            "b_params": 2,
            "c_params": 2,
            "blocked_params": 0,
            "dc_test_items": 4,
            "ac_test_items": 2,
            "ldo_test_items": 0,
            "warnings": [],
            "errors": [],
            "pin_definitions": list(self.pin_definitions),
            "parameters": [{"param_name": "VIH"}, {"param_name": "VOL"}],
        }


class _FakeMappingResult:
    status = "success"
    chip_name = "HD74LS00P"
    chip_type = "digital"
    adapter_model = "Y.SH.8281-13"
    warnings = []
    errors = []
    resource_mappings = [{"resource_type": "DIO", "channel_no": 0, "signal_type": "IN"}]
    pgs_configs = [{"function_name": "CON"}]

    def model_dump(self):
        return {
            "status": "success",
            "chip_name": self.chip_name,
            "chip_type": self.chip_type,
            "adapter_model": self.adapter_model,
            "warnings": [],
            "errors": [],
            "resource_mappings": list(self.resource_mappings),
            "pgs_configs": list(self.pgs_configs),
            "pgs_detail_conditions": [],
            "pin_groups": {},
            "adapter_info": {},
        }


class _FakeTestPlanService:
    def extract_from_pdf(self, pdf_path, pages=None, max_workers=5):
        return _FakeExtractResult()


class _FakeResourceMappingService:
    def generate_resource_map(self, extraction_result, pin_mapping_df, dual_site=False):
        return _FakeMappingResult()


class _FakePlanner:
    def build_plan(self, **kwargs):
        return {
            "scenario": "digital",
            "selected_items": list(kwargs["test_items"]),
            "requires_vector": True,
            "requires_pgs": True,
            "resources": ["DIO", "PMU"],
            "items": [],
            "warnings": [],
            "errors": [],
        }


class _FakeCodegenService:
    def generate(self, **kwargs):
        return {
            "code": "DUT_API int CON(short site, LPCTSTR name) { return 0; }",
            "filename": "HD74LS00P_test.cpp",
            "functions": 1,
            "lines": 1,
            "chip_name": "HD74LS00P",
            "chip_type": "digital",
            "test_items": list(kwargs["test_items"]),
        }


class _FakeStaticValidation:
    class _Result:
        def to_dict(self):
            return {"passed": True, "score": 95}

    def validate(self, code):
        return self._Result()


class _FakeCompileValidation:
    def validate(self, code, filename):
        return {"passed": True, "attempted": True, "mode": "simulated_compile_check"}


class _FakeKnowledge:
    def recommend_test_items(self, chip_type, param_names=None):
        return ["CON", "VIH", "VOL"]

    def resolve_scenario(self, chip_type):
        return "digital"


class _FakeRag:
    is_ready = False

    def retrieve(self, query, top_k=5, **kwargs):
        return []


class _FakeTestProgramService:
    def export_package(self, **kwargs):  # pragma: no cover - export disabled in this test
        raise AssertionError("export_package should be skipped in this test")


def test_full_ate_development_flow_reaches_review_and_skips_packager(tmp_path):
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 demo")

    controller = build_full_ate_development_controller(
        testplan_service=_FakeTestPlanService(),
        resource_mapping_service=_FakeResourceMappingService(),
        planner=_FakePlanner(),
        codegen_service=_FakeCodegenService(),
        static_validator=_FakeStaticValidation(),
        compile_validator=_FakeCompileValidation(),
        testprogram_service=_FakeTestProgramService(),
        knowledge=_FakeKnowledge(),
        rag_service=_FakeRag(),
    )

    run = controller.run_flow(
        flow_name="full_ate_development",
        payload={
            "goal": "根据 Datasheet 生成 STS8200S 测试工程",
            "pdf_path": str(pdf_path),
            "chip_type": "digital",
            "test_items": [],
            "user_prompt": "生成可复核的测试程序",
            "export_package": False,
        },
    )

    assert run.status == "human_review_required"
    assert [step["agent"] for step in run.steps][-2:] == ["review_agent", "engineering_packager"]
    assert run.steps[-1]["status"] == "skipped"
    assert run.shared["review"]["overall_status"] == "needs_human_review"
    rag_artifact = next(item for item in run.artifacts if item["type"] == "rag_context")
    assert rag_artifact["summary"]["fallback_used"] is True


class _NoPinExtractResult(_FakeExtractResult):
    pin_definitions = []

    def model_dump(self):
        data = super().model_dump()
        data["pin_definitions"] = []
        return data


class _NoPinTestPlanService:
    def extract_from_pdf(self, pdf_path, pages=None, max_workers=5):
        return _NoPinExtractResult()


def test_full_ate_development_flow_stops_for_human_review_when_pin_data_missing(tmp_path):
    pdf_path = tmp_path / "demo.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 demo")

    controller = build_full_ate_development_controller(
        testplan_service=_NoPinTestPlanService(),
        resource_mapping_service=_FakeResourceMappingService(),
        planner=_FakePlanner(),
        codegen_service=_FakeCodegenService(),
        static_validator=_FakeStaticValidation(),
        compile_validator=_FakeCompileValidation(),
        testprogram_service=_FakeTestProgramService(),
        knowledge=_FakeKnowledge(),
        rag_service=_FakeRag(),
    )

    run = controller.run_flow(
        flow_name="full_ate_development",
        payload={
            "goal": "根据 Datasheet 生成 STS8200S 测试工程",
            "pdf_path": str(pdf_path),
            "chip_type": "digital",
            "export_package": False,
        },
    )

    assert run.status == "human_review_required"
    assert [step["agent"] for step in run.steps] == ["input_resolver", "testplan_extractor", "param_validator"]
    assert run.steps[-1]["requires_human_review"] is True
    assert run.steps[-1]["message"] == "Extraction needs engineer review before continuing."
    assert run.steps[-1]["next_action"] == "Review extracted pin definitions and required power pins."
    assert run.steps[-1]["warnings"]

from app.services.review_service import ReviewService


def test_review_service_accepts_integer_function_count():
    service = ReviewService()

    review_input = service._build_review_input(
        {
            "generated_result": {
                "filename": "demo.cpp",
                "functions": 3,
                "plan": {},
                "static_analysis": {},
                "compile_validation": {},
            }
        },
        steps=[],
    )

    assert review_input["generated_code"]["function_count"] == 3


def test_review_service_demotes_rag_and_warning_counts_to_recommendations():
    service = ReviewService()

    review = service.generate_review(
        {
            "validation": {"passed": True, "warnings": ["missing power hint"]},
            "rag": {"hit_count": 0, "ready": True, "fallback_used": False},
            "resource_map_result": {"warnings": ["bidir pin review needed"], "errors": []},
            "generated_result": {
                "filename": "demo.cpp",
                "functions": 3,
                "plan": {"requires_vector": False, "requires_pgs": False},
                "static_analysis": {"passed": True, "issues": []},
                "compile_validation": {"attempted": False, "passed": False, "diagnostics": ["no compiler"]},
            },
        },
        steps=[],
    )

    assert "参数校验未完全通过" not in " ".join(review["must_review_items"])
    assert any("RAG 检索未命中" in item for item in review["recommendations"])
    assert any("参数校验中有 1 个警告" in item for item in review["recommendations"])
    assert any("资源映射中有 1 个警告" in item for item in review["recommendations"])
    assert any("未执行真实编译预检" in item for item in review["recommendations"])


def test_review_service_keeps_compile_failure_as_blocking_item():
    service = ReviewService()

    review = service.generate_review(
        {
            "validation": {"passed": True, "warnings": []},
            "rag": {"hit_count": 2, "ready": True, "fallback_used": False},
            "generated_result": {
                "filename": "demo.cpp",
                "functions": 3,
                "plan": {"requires_vector": True, "requires_pgs": True},
                "static_analysis": {"passed": True, "issues": []},
                "compile_validation": {"attempted": True, "passed": False, "diagnostics": ["syntax error"]},
            },
        },
        steps=[],
    )

    assert review["risk_level"] == "high"
    assert any("编译预检未通过" in item for item in review["must_review_items"])
    assert any("VECDIO/PGS" in item for item in review["must_review_items"])

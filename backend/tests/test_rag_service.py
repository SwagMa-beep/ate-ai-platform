import app.services.rag_service as rag_module
from app.services.rag_service import RAGService, STS8200S_BUILTIN_KNOWLEDGE


def test_rag_query_variants_expand_generic_goal_into_handbook_terms(monkeypatch):
    monkeypatch.setattr(rag_module, "CHROMADB_AVAILABLE", False)

    service = RAGService()
    service.build_index_from_text(STS8200S_BUILTIN_KNOWLEDGE)

    variants = service.build_query_variants(
        "生成ATE测试程序",
        chip_name="HD74LS00P",
        chip_type="digital",
        test_items=["FUN", "VIH"],
    )

    assert variants
    assert any("STS8200S" in variant for variant in variants)
    assert any("RunVector" in variant or "DIO" in variant for variant in variants)
    assert any("VIH" in variant for variant in variants)


def test_rag_retrieve_uses_enriched_query_to_find_builtin_context(monkeypatch):
    monkeypatch.setattr(rag_module, "CHROMADB_AVAILABLE", False)

    service = RAGService()
    service.build_index_from_text(STS8200S_BUILTIN_KNOWLEDGE)

    results = service.retrieve(
        "帮我生成ATE程序",
        top_k=3,
        chip_name="HD74LS00P",
        chip_type="digital",
        test_items=["FUN", "VIH"],
    )

    assert results
    assert all(result.get("matched_query") for result in results)
    assert any(
        any(token in result["text"] for token in ["RunVector", "DIO", "StsGetParam", "SetTestResult"])
        for result in results
    )

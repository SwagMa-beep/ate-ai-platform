from app.services.enterprise_code_knowledge import get_enterprise_code_knowledge_service


def test_enterprise_code_knowledge_loads_items():
    svc = get_enterprise_code_knowledge_service()
    summary = svc.summary()

    assert summary["sample_count"] >= 3
    assert "CON" in summary["digital_items"]
    assert "UVLO" in summary["analog_items"]


def test_recommendation_from_chip_type_returns_enterprise_items():
    svc = get_enterprise_code_knowledge_service()

    digital_items = svc.recommend_test_items("DIGITAL_74")
    analog_items = svc.recommend_test_items("LDO")

    assert "VIK" in digital_items
    assert "TP1" in digital_items
    assert "UVLO" in analog_items

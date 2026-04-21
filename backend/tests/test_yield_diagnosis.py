from app.services.yield_diagnosis import YieldDiagnosisService


def test_yield_diagnosis_returns_bounded_metrics():
    result = YieldDiagnosisService().run_diagnosis(
        n_samples=80,
        inject_anomaly=True,
        anomaly_ratio=0.1,
        channel=2,
    ).to_dict()

    assert 60.0 <= result["yield_rate"] <= 99.9
    assert result["sample_count"] == 80
    assert 0.0 <= result["anomaly_ratio"] <= 1.0
    assert result["model_backend"] in {"IsolationForest", "Rule-Based"}
    assert len(result["waveform"]) > 0


def test_yield_diagnosis_waveform_endpoint_shape():
    result = YieldDiagnosisService().run_diagnosis(
        n_samples=20,
        inject_anomaly=False,
    ).to_dict()

    first = result["waveform"][0]
    assert set(first) == {"t", "v", "i", "flag"}

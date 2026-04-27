from app.main import app


def test_agent_run_routes_are_mounted():
    paths = {route.path for route in app.routes}
    assert "/api/v1/agent-runs" in paths
    assert "/api/v1/agent-runs/{run_id}" in paths
    assert "/api/v1/agent-runs/{run_id}/artifacts" in paths


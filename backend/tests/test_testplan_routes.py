from app.main import app


def test_testplan_task_center_routes_are_mounted():
    paths = {route.path for route in app.routes}
    assert "/api/v1/testplan/tasks" in paths
    assert "/api/v1/testplan/retry/{task_id}" in paths
    assert "/api/v1/testplan/cancel/{task_id}" in paths

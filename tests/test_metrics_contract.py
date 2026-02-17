from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from threading import Event


def _load_run_live_module():
    module_name = "run_live_script_metrics"
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_live.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed_to_load_run_live_module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


run_live_script = _load_run_live_module()


def test_metrics_render_contains_required_series():
    state = run_live_script.RuntimeMetricsState(
        stop_event=Event(),
        run_loop_total=7,
        run_loop_failures_total=2,
        monitor_status="reconnecting",
    )

    metrics = run_live_script._render_metrics(state)

    assert "run_loop_total" in metrics
    assert "run_loop_failures_total" in metrics
    assert "monitor_status" in metrics
    assert 'monitor_status{status="reconnecting"} 2' in metrics


def test_health_and_metrics_coexist(tmp_path):
    state = run_live_script.RuntimeMetricsState(stop_event=Event())
    server = run_live_script._run_runtime_server(state, 19754)
    try:
        import urllib.request

        health = urllib.request.urlopen("http://127.0.0.1:19754/healthz", timeout=3)
        metrics = urllib.request.urlopen("http://127.0.0.1:19754/metrics", timeout=3)

        assert health.status == 200
        text = metrics.read().decode("utf-8")
        assert "run_loop_total" in text
        assert "run_loop_failures_total" in text
        assert "monitor_status" in text
    finally:
        server.shutdown()
        server.server_close()

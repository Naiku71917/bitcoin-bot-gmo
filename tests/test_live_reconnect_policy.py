from __future__ import annotations

import importlib.util
import sys
from threading import Event
from pathlib import Path


def _load_run_live_module():
    module_name = "run_live_script"
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_live.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed_to_load_run_live_module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


run_live_script = _load_run_live_module()


def test_reconnect_policy_recovers_and_returns_active(monkeypatch, tmp_path):
    events: list[dict] = []

    def _capture_progress(**kwargs):
        events.append(kwargs)
        return kwargs

    monkeypatch.setattr(run_live_script, "emit_run_progress", _capture_progress)

    stop_event = Event()
    call_count = 0

    def _run_once_then_succeed(*, mode: str, config_path: str):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("temporary network error")
        stop_event.set()
        return {"status": "success"}

    exit_code, reconnect_count = run_live_script._run_daemon_loop(
        stop_event=stop_event,
        config_path="configs/runtime.live.spot.yaml",
        artifacts_dir=str(tmp_path / "artifacts"),
        interval_seconds=0,
        max_reconnect_retries=3,
        reconnect_wait_seconds=0,
        run_func=_run_once_then_succeed,
    )

    assert exit_code == 0
    assert reconnect_count == 1
    assert any(event["monitor_status"] == "reconnecting" for event in events)
    assert any(event["monitor_status"] == "active" for event in events)


def test_reconnect_policy_fails_after_retry_limit(monkeypatch, tmp_path):
    events: list[dict] = []

    def _capture_progress(**kwargs):
        events.append(kwargs)
        return kwargs

    monkeypatch.setattr(run_live_script, "emit_run_progress", _capture_progress)

    stop_event = Event()

    def _always_fail(*, mode: str, config_path: str):
        raise RuntimeError("persistent exchange outage")

    exit_code, reconnect_count = run_live_script._run_daemon_loop(
        stop_event=stop_event,
        config_path="configs/runtime.live.spot.yaml",
        artifacts_dir=str(tmp_path / "artifacts"),
        interval_seconds=0,
        max_reconnect_retries=0,
        reconnect_wait_seconds=0,
        run_func=_always_fail,
    )

    assert exit_code == 1
    assert reconnect_count == 1
    assert any(event["monitor_status"] == "reconnecting" for event in events)
    assert any(event["status"] == "failed" for event in events)
    assert events[-1]["monitor_status"] == "degraded"

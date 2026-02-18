from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from threading import Event


def _load_run_live_module():
    module_name = "run_live_script_failover"
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_live.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed_to_load_run_live_module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


run_live_script = _load_run_live_module()


def _assert_case(condition: bool, *, case_name: str, transitions: list[dict]) -> None:
    assert condition, f"case={case_name} transitions={transitions}"


def test_failover_case_stream_reconnecting_to_active(tmp_path):
    case_name = "stream_reconnecting_to_active"
    transitions: list[dict] = []
    stop_event = Event()

    call_count = 0

    def _stream_recover(*, mode: str, config_path: str):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"pipeline_summary": {"monitor_summary": {"status": "reconnecting"}}}
        stop_event.set()
        return {"pipeline_summary": {"monitor_summary": {"status": "active"}}}

    exit_code, reconnect_count = run_live_script._run_daemon_loop(
        stop_event=stop_event,
        config_path="configs/runtime.live.spot.yaml",
        artifacts_dir=str(tmp_path / "artifacts"),
        interval_seconds=0,
        max_reconnect_retries=3,
        reconnect_wait_seconds=0,
        run_func=_stream_recover,
        transition_logger=transitions.append,
    )

    _assert_case(exit_code == 0, case_name=case_name, transitions=transitions)
    _assert_case(reconnect_count == 0, case_name=case_name, transitions=transitions)
    _assert_case(
        any(item["monitor_status"] == "reconnecting" for item in transitions),
        case_name=case_name,
        transitions=transitions,
    )


def test_failover_case_execution_failure_exceeds_retry_limit(tmp_path):
    case_name = "execution_failure_exceeds_retry_limit"
    transitions: list[dict] = []
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
        transition_logger=transitions.append,
    )

    _assert_case(exit_code == 1, case_name=case_name, transitions=transitions)
    _assert_case(reconnect_count == 1, case_name=case_name, transitions=transitions)
    _assert_case(
        any(item["monitor_status"] == "reconnecting" for item in transitions),
        case_name=case_name,
        transitions=transitions,
    )
    _assert_case(
        any(
            item["monitor_status"] == "degraded" and item["status"] == "failed"
            for item in transitions
        ),
        case_name=case_name,
        transitions=transitions,
    )


def test_failover_case_execution_failure_then_active_recovery(tmp_path):
    case_name = "execution_failure_then_active_recovery"
    transitions: list[dict] = []
    stop_event = Event()

    call_count = 0

    def _fail_once_then_recover(*, mode: str, config_path: str):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("temporary stream drop")
        stop_event.set()
        return {"pipeline_summary": {"monitor_summary": {"status": "active"}}}

    exit_code, reconnect_count = run_live_script._run_daemon_loop(
        stop_event=stop_event,
        config_path="configs/runtime.live.spot.yaml",
        artifacts_dir=str(tmp_path / "artifacts"),
        interval_seconds=0,
        max_reconnect_retries=3,
        reconnect_wait_seconds=0,
        run_func=_fail_once_then_recover,
        transition_logger=transitions.append,
    )

    _assert_case(exit_code == 0, case_name=case_name, transitions=transitions)
    _assert_case(reconnect_count == 1, case_name=case_name, transitions=transitions)
    _assert_case(
        any(item["monitor_status"] == "reconnecting" for item in transitions),
        case_name=case_name,
        transitions=transitions,
    )
    _assert_case(
        any(
            item["monitor_status"] == "active" and item["status"] == "running"
            for item in transitions
        ),
        case_name=case_name,
        transitions=transitions,
    )

from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from typing import Callable

from bitcoin_bot.config.loader import load_runtime_config
from bitcoin_bot.config.validator import validate_config, validate_runtime_environment
from bitcoin_bot.main import run
from bitcoin_bot.telemetry.reporters import emit_run_progress, monitor_status_to_value
from bitcoin_bot.utils.logging import set_audit_log_policy


@dataclass(slots=True)
class RuntimeMetricsState:
    stop_event: Event
    run_loop_total: int = 0
    run_loop_failures_total: int = 0
    monitor_status: str = "active"


def _render_metrics(state: RuntimeMetricsState) -> str:
    lines = [
        "# HELP run_loop_total Total number of loop iterations.",
        "# TYPE run_loop_total counter",
        f"run_loop_total {state.run_loop_total}",
        "# HELP run_loop_failures_total Total number of loop failures.",
        "# TYPE run_loop_failures_total counter",
        f"run_loop_failures_total {state.run_loop_failures_total}",
        "# HELP monitor_status Current monitor status as numeric gauge (degraded=0, active=1, reconnecting=2).",
        "# TYPE monitor_status gauge",
        f'monitor_status{{status="{state.monitor_status}"}} {monitor_status_to_value(state.monitor_status)}',
    ]
    return "\n".join(lines) + "\n"


class _RuntimeHandler(BaseHTTPRequestHandler):
    runtime_state: RuntimeMetricsState

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            status_code = 200 if not self.runtime_state.stop_event.is_set() else 503
            self.send_response(status_code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok" if status_code == 200 else b"shutting_down")
            return

        if self.path == "/metrics":
            payload = _render_metrics(self.runtime_state).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            return

    def log_message(self, format: str, *args: object) -> None:
        return


def _run_runtime_server(
    runtime_state: RuntimeMetricsState, port: int
) -> ThreadingHTTPServer:
    _RuntimeHandler.runtime_state = runtime_state
    server = ThreadingHTTPServer(("0.0.0.0", port), _RuntimeHandler)
    server.daemon_threads = True
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5})
    thread.daemon = True
    thread.start()
    return server


def _install_signal_handlers(stop_event: Event) -> None:
    def _handle_signal(signum: int, _frame: object | None) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)


def _run_daemon_loop(
    *,
    stop_event: Event,
    config_path: str,
    artifacts_dir: str,
    interval_seconds: int,
    max_reconnect_retries: int,
    reconnect_wait_seconds: int,
    runtime_state: RuntimeMetricsState | None = None,
    run_func: Callable[..., dict] | None = None,
) -> tuple[int, int]:
    execute_run = run_func or run
    exit_code = 0
    reconnect_count = 0
    metrics_state = runtime_state or RuntimeMetricsState(stop_event=stop_event)

    while not stop_event.is_set():
        metrics_state.run_loop_total += 1
        try:
            run_result = execute_run(mode="live", config_path=config_path)
            resolved_monitor_status = (
                run_result.get("pipeline_summary", {})
                .get("monitor_summary", {})
                .get("status", "active")
                if isinstance(run_result, dict)
                else "active"
            )
            if resolved_monitor_status not in {"active", "reconnecting", "degraded"}:
                resolved_monitor_status = "active"
            metrics_state.monitor_status = resolved_monitor_status
            if reconnect_count > 0:
                emit_run_progress(
                    artifacts_dir=artifacts_dir,
                    mode="live",
                    status="running",
                    last_error=None,
                    monitor_status=resolved_monitor_status,
                    reconnect_count=reconnect_count,
                )
        except Exception as exc:
            reconnect_count += 1
            metrics_state.run_loop_failures_total += 1
            metrics_state.monitor_status = "reconnecting"
            emit_run_progress(
                artifacts_dir=artifacts_dir,
                mode="live",
                status="degraded",
                last_error="reconnecting_after_error",
                monitor_status="reconnecting",
                reconnect_count=reconnect_count,
            )
            if reconnect_count > max_reconnect_retries:
                metrics_state.monitor_status = "degraded"
                emit_run_progress(
                    artifacts_dir=artifacts_dir,
                    mode="live",
                    status="failed",
                    last_error=str(exc),
                    monitor_status="degraded",
                    reconnect_count=reconnect_count,
                )
                exit_code = 1
                stop_event.set()
                break

            stop_event.wait(reconnect_wait_seconds)
            continue

        stop_event.wait(interval_seconds)

    return exit_code, reconnect_count


def main() -> int:
    stop_event = Event()
    _install_signal_handlers(stop_event)

    config_path = os.getenv("CONFIG_PATH", "configs/runtime.live.spot.yaml")
    validated = validate_config(load_runtime_config(config_path))
    interval_seconds = int(os.getenv("LIVE_LOOP_INTERVAL_SECONDS", "60"))
    reconnect_wait_seconds = int(os.getenv("LIVE_RECONNECT_WAIT_SECONDS", "5"))
    max_reconnect_retries = int(os.getenv("LIVE_MAX_RECONNECT_RETRIES", "3"))
    health_port = int(os.getenv("HEALTH_PORT", "9754"))
    artifacts_dir = os.getenv("ARTIFACTS_DIR", validated.paths.artifacts_dir)
    audit_max_bytes = int(os.getenv("AUDIT_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    audit_retention = int(os.getenv("AUDIT_LOG_RETENTION", "5"))

    set_audit_log_policy(max_bytes=audit_max_bytes, retention=audit_retention)

    env_validation = validate_runtime_environment(validated)
    if env_validation["fatal_errors"]:
        emit_run_progress(
            artifacts_dir=artifacts_dir,
            mode="live",
            status="failed",
            last_error=env_validation["fatal_errors"][0],
            monitor_status="degraded",
            validation=env_validation,
        )
        return 1

    if env_validation["warnings"]:
        emit_run_progress(
            artifacts_dir=artifacts_dir,
            mode="live",
            status="running",
            last_error=env_validation["warnings"][0],
            monitor_status="active",
            validation=env_validation,
        )

    runtime_state = RuntimeMetricsState(stop_event=stop_event)
    health_server = _run_runtime_server(runtime_state, health_port)
    exit_code = 1
    reconnect_count = 0
    try:
        exit_code, reconnect_count = _run_daemon_loop(
            stop_event=stop_event,
            config_path=config_path,
            artifacts_dir=artifacts_dir,
            interval_seconds=interval_seconds,
            max_reconnect_retries=max_reconnect_retries,
            reconnect_wait_seconds=reconnect_wait_seconds,
            runtime_state=runtime_state,
        )
    finally:
        final_status = "failed" if exit_code != 0 else "degraded"
        final_error = "runtime_exception" if exit_code != 0 else "shutdown_signal"
        runtime_state.monitor_status = "degraded"
        emit_run_progress(
            artifacts_dir=artifacts_dir,
            mode="live",
            status=final_status,
            last_error=final_error,
            monitor_status="degraded",
            reconnect_count=reconnect_count,
            validation=env_validation,
        )
        stop_event.set()
        health_server.shutdown()
        health_server.server_close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

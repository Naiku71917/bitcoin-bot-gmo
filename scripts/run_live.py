from __future__ import annotations

import os
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

from bitcoin_bot.main import run
from bitcoin_bot.telemetry.reporters import emit_run_progress


class _HealthHandler(BaseHTTPRequestHandler):
    stop_event: Event

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            return

        status_code = 200 if not self.stop_event.is_set() else 503
        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok" if status_code == 200 else b"shutting_down")

    def log_message(self, format: str, *args: object) -> None:
        return


def _run_health_server(stop_event: Event, port: int) -> ThreadingHTTPServer:
    _HealthHandler.stop_event = stop_event
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
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


def main() -> int:
    stop_event = Event()
    _install_signal_handlers(stop_event)

    config_path = os.getenv("CONFIG_PATH", "configs/runtime.live.spot.yaml")
    interval_seconds = int(os.getenv("LIVE_LOOP_INTERVAL_SECONDS", "60"))
    health_port = int(os.getenv("HEALTH_PORT", "9754"))
    artifacts_dir = os.getenv("ARTIFACTS_DIR", "./var/artifacts")

    health_server = _run_health_server(stop_event, health_port)
    exit_code = 0
    reconnect_count = 0
    try:
        while not stop_event.is_set():
            try:
                run(mode="live", config_path=config_path)
            except Exception as exc:
                reconnect_count += 1
                emit_run_progress(
                    artifacts_dir=artifacts_dir,
                    mode="live",
                    status="degraded",
                    last_error="reconnecting_after_error",
                    monitor_status="reconnecting",
                    reconnect_count=reconnect_count,
                )
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
            stop_event.wait(interval_seconds)
    finally:
        final_status = "failed" if exit_code != 0 else "degraded"
        final_error = "runtime_exception" if exit_code != 0 else "shutdown_signal"
        emit_run_progress(
            artifacts_dir=artifacts_dir,
            mode="live",
            status=final_status,
            last_error=final_error,
            monitor_status="degraded",
            reconnect_count=reconnect_count,
        )
        stop_event.set()
        health_server.shutdown()
        health_server.server_close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

from bitcoin_bot.main import run


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

    health_server = _run_health_server(stop_event, health_port)
    try:
        while not stop_event.is_set():
            run(mode="live", config_path=config_path)
            stop_event.wait(interval_seconds)
    finally:
        stop_event.set()
        health_server.shutdown()
        health_server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import cast

from bitcoin_bot.config.loader import load_runtime_config
from bitcoin_bot.config.models import Mode
from bitcoin_bot.config.validator import validate_config
from bitcoin_bot.pipeline.backtest_runner import run_backtest
from bitcoin_bot.pipeline.live_runner import run_live
from bitcoin_bot.pipeline.paper_runner import run_paper
from bitcoin_bot.telemetry.reporters import emit_run_complete


def run(mode: Mode, config_path: str) -> dict:
    started_at = datetime.now(UTC)
    runtime_config = load_runtime_config(config_path)
    runtime_config.runtime.mode = mode
    validated = validate_config(runtime_config)

    if validated.runtime.mode == "backtest":
        pipeline = run_backtest(validated)
    elif validated.runtime.mode == "paper":
        pipeline = run_paper(validated)
    elif validated.runtime.mode == "live":
        pipeline = run_live(validated)
    else:
        raise ValueError(f"Unsupported mode: {validated.runtime.mode}")

    completed_at = datetime.now(UTC)
    return emit_run_complete(
        mode=validated.runtime.mode,
        started_at=started_at,
        completed_at=completed_at,
        pipeline_result=pipeline,
        artifacts_dir=validated.paths.artifacts_dir,
        discord_enabled=validated.notify.discord.enabled,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="bitcoin-bot-gmo")
    parser.add_argument("--config", default="configs/runtime.example.yaml")
    parser.add_argument("--mode", choices=["backtest", "paper", "live"], default="live")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    run(mode=cast(Mode, args.mode), config_path=args.config)


if __name__ == "__main__":
    main()

from __future__ import annotations

import math

from bitcoin_bot.config.models import RuntimeConfig
from bitcoin_bot.data.ohlcv import load_ohlcv_for_backtest
from bitcoin_bot.optimizer.orchestrator import score_from_backtest_metrics


REPLAY_SUMMARY_KEYS = (
    "mode",
    "symbol",
    "product_type",
    "return",
    "max_drawdown",
    "win_rate",
    "profit_factor",
    "trade_count",
)


def run_backtest(config: RuntimeConfig) -> dict:
    frame, data_source, fallback_reason = load_ohlcv_for_backtest(
        csv_path=config.data.csv_path,
        symbol=config.exchange.symbol,
        timeframe=config.data.timeframe,
        backtest_data_quality_mode=config.data.backtest_data_quality_mode,
    )

    closes = frame["close"].astype(float)
    close_returns = closes.pct_change().dropna()

    if close_returns.empty:
        return_metric = 0.0
        max_drawdown = 0.0
        win_rate = 0.0
        profit_factor = 0.0
        trade_count = 0.0
    else:
        return_metric = float((closes.iloc[-1] / closes.iloc[0]) - 1.0)
        equity_curve = (1.0 + close_returns).cumprod()
        drawdown_series = (equity_curve / equity_curve.cummax()) - 1.0
        max_drawdown = abs(float(drawdown_series.min()))

        positive_returns = close_returns[close_returns > 0.0]
        negative_returns = close_returns[close_returns < 0.0]
        win_rate = float((close_returns > 0.0).mean())
        gross_profit = float(positive_returns.sum())
        gross_loss = abs(float(negative_returns.sum()))
        profit_factor = (
            gross_profit / gross_loss if gross_loss > 1e-12 else gross_profit
        )
        trade_count = float((close_returns.abs() > 0.0).sum())

    metrics = {
        "return": return_metric,
        "max_drawdown": min(max(max_drawdown, 0.0), 1.0),
        "win_rate": min(max(win_rate, 0.0), 1.0),
        "profit_factor": max(profit_factor, 0.0),
        "trade_count": max(trade_count, 0.0),
    }

    if not math.isfinite(metrics["profit_factor"]):
        metrics["profit_factor"] = 0.0

    return {
        "status": "success",
        "summary": {
            "mode": "backtest",
            "symbol": config.exchange.symbol,
            "product_type": config.exchange.product_type,
            "data_source": data_source,
            "data_points": int(len(frame)),
            "data_fallback_reason": fallback_reason,
            **metrics,
        },
        "optimization_score": score_from_backtest_metrics(metrics),
    }


def extract_replay_summary(pipeline_result: dict) -> dict:
    summary = dict(pipeline_result.get("summary", {}))
    return {key: summary.get(key) for key in REPLAY_SUMMARY_KEYS}

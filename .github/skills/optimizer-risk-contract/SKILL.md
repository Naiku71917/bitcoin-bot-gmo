# Skill: optimizer-risk-contract

## 目的
最適化スナップショット契約（score/gates/salvage）とリスクガード判定（success/degraded/abort）を維持する。

## 前提（必須）
- このSkill適用時は Serena MCP で `optimizer/orchestrator.py` と `optimizer/gates.py`、関連テストを先に確認する。

## 使うタイミング
- `score_from_backtest_metrics()` のスコア式を変更する時
- `build_optimization_snapshot()` の payload を変更する時
- `evaluate_optimization_gates()` / `evaluate_risk_guards()` の判定ロジックを変更する時

## 主な編集対象
- `src/bitcoin_bot/optimizer/orchestrator.py`
- `src/bitcoin_bot/optimizer/gates.py`
- `src/bitcoin_bot/pipeline/backtest_runner.py`
- `src/bitcoin_bot/pipeline/live_runner.py`
- `tests/test_optimizer_contract.py`
- `tests/test_backtest_metrics_contract.py`
- `tests/test_risk_guards.py`

## 実行手順
1. optimization 出力の `score`, `gates.accept`, `gates.reasons`, `salvage` を維持。
2. `opt_trials_executed` が run complete 側へ反映される経路を維持。
3. risk guard の reason code（例: `max_drawdown_exceeded`）を後方互換で扱う。
4. live runner の `stop_reason_codes` と `risk_guards` summary の整合を維持。

## 完了条件
- `pytest -q tests/test_optimizer_contract.py tests/test_backtest_metrics_contract.py tests/test_risk_guards.py` が通る。

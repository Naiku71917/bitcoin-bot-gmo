# Skill: run-complete-contract

## 目的
`run_complete` 出力契約を維持したまま、終了ペイロードや通知連携を安全に変更する。

## 前提（必須）
- このSkill適用時は Serena MCP で対象シンボルと関連テストを先に確認する。

## 使うタイミング
- `emit_run_complete()` の payload 形状を変更する時
- `atomic_dump_json` 出力先や出力手順を変更する時
- Discord通知の結果を payload に反映する時
- `pipeline_summary.opt_trials_executed` や `optimization.*` 契約を変更する時

## 主な編集対象
- `src/bitcoin_bot/telemetry/reporters.py`
- `src/bitcoin_bot/utils/io.py`
- `src/bitcoin_bot/main.py`
- `tests/test_main_contract.py`
- `tests/test_discord_non_fatal.py`（通知仕様に影響する場合）
- `tests/test_optimizer_contract.py`
- `tests/test_backtest_metrics_contract.py`

## 実行手順
1. `main.run()` から `emit_run_complete()` までの呼び出し引数を確認。
2. payloadの必須トップレベル（`run_id`, `pipeline`, `pipeline_summary`, `optimization`, `notifications`）を維持。
3. `var/artifacts/run_complete.json` が atomic write されることを維持。
4. 標準出力マーカー `BEGIN_RUN_COMPLETE_JSON` / `END_RUN_COMPLETE_JSON` を維持。
5. `optimization` の `score` / `gates.accept` / `gates.reasons` / `salvage` を維持。
6. Discord失敗を非致命で保持（`status`, `reason`）し、例外で落とさない。

## 非交渉契約
- `var/artifacts/run_complete.json` は `atomic_dump_json` で更新する。
- STDOUTマーカー `BEGIN_RUN_COMPLETE_JSON` / `END_RUN_COMPLETE_JSON` を維持する。

## 完了条件
- `pytest -q tests/test_main_contract.py tests/test_optimizer_contract.py tests/test_backtest_metrics_contract.py tests/test_discord_non_fatal.py` が通る。
- run後に `var/artifacts/run_complete.json` が生成される。

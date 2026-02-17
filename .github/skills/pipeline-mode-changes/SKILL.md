# Skill: pipeline-mode-changes

## 目的
`backtest|paper|live` のmode分岐とrunner実装を変更する際に、メインフロー契約と運用監視を壊さない。

## 前提（必須）
- このSkill適用時は Serena MCP で `main.py` と3つの runner、関連テストを先に確認する。

## 使うタイミング
- `main.py` の mode 分岐を変更する時
- `pipeline/*_runner.py` の返却形式を変更する時
- live運用時のheartbeat挙動を変更する時
- `emit_run_progress()` 経由の `run_progress.json` 更新契約を変更する時

## 主な編集対象
- `src/bitcoin_bot/main.py`
- `src/bitcoin_bot/pipeline/backtest_runner.py`
- `src/bitcoin_bot/pipeline/paper_runner.py`
- `src/bitcoin_bot/pipeline/live_runner.py`
- `src/bitcoin_bot/telemetry/reporters.py`
- `tests/test_main_contract.py`
- `tests/test_paper_runner_contract.py`
- `tests/test_live_monitor_contract.py`
- `tests/test_live_progress_contract.py`
- `docker-compose.yml`（healthcheck条件に影響する場合）

## 実行手順
1. `main.run()` の分岐条件を `runtime.mode` に対して維持。
2. 各runnerの返却を `{"status": ..., "summary": ...}` 契約で統一。
3. paper は `paper_order_events` と `summary.order_count` の整合を維持。
4. live は `run_progress.json` の `monitor_status`/`reconnect_count` と heartbeat 更新を維持。
5. 新modeを追加する場合は parser の choices / validator / tests を同時更新。
6. 最終的に `emit_run_complete()` 経由で同じ run完了契約に到達させる。

## 完了条件
- `pytest -q tests/test_main_contract.py tests/test_paper_runner_contract.py tests/test_live_progress_contract.py tests/test_live_monitor_contract.py` が通る。
- live実行で heartbeat が更新される。

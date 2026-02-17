# Skill: pipeline-mode-changes

## 目的
`backtest|paper|live` のmode分岐とrunner実装を変更する際に、メインフロー契約と運用監視を壊さない。

## 使うタイミング
- `main.py` の mode 分岐を変更する時
- `pipeline/*_runner.py` の返却形式を変更する時
- live運用時のheartbeat挙動を変更する時

## 主な編集対象
- `src/bitcoin_bot/main.py`
- `src/bitcoin_bot/pipeline/backtest_runner.py`
- `src/bitcoin_bot/pipeline/paper_runner.py`
- `src/bitcoin_bot/pipeline/live_runner.py`
- `tests/test_main_contract.py`
- `docker-compose.yml`（healthcheck条件に影響する場合）

## 実行手順
1. `main.run()` の分岐条件を `runtime.mode` に対して維持。
2. 各runnerの返却を `{"status": ..., "summary": ...}` 契約で統一。
3. liveは `var/artifacts/heartbeat.txt` 更新の運用契約を維持。
4. 新modeを追加する場合は parser の choices / validator / tests を同時更新。
5. 最終的に `emit_run_complete()` 経由で同じ run完了契約に到達させる。

## 完了条件
- `pytest -q tests/test_main_contract.py` が通る。
- live実行で heartbeat が更新される。

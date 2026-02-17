# Skill: live-runtime-ops

## 目的
`scripts/run_live.py` のデーモン運用契約（再接続、進捗、health、metrics、環境検証）を維持して変更する。

## 前提（必須）
- このSkill適用時は Serena MCP で `scripts/run_live.py` と live系テスト群を先に確認する。

## 使うタイミング
- `_run_daemon_loop()` の再接続ポリシーを変更する時
- `emit_run_progress()` への送信内容（monitor_status/reconnect_count）を変更する時
- `/healthz` / `/metrics` の仕様を変更する時
- `validate_runtime_environment()` 起因の開始失敗条件を変更する時

## 主な編集対象
- `scripts/run_live.py`
- `src/bitcoin_bot/telemetry/reporters.py`
- `src/bitcoin_bot/config/validator.py`
- `tests/test_live_monitor_contract.py`
- `tests/test_live_reconnect_policy.py`
- `tests/test_live_progress_contract.py`
- `tests/test_metrics_contract.py`
- `tests/test_runtime_env_validation.py`

## 実行手順
1. `/healthz` と `/metrics` の両エンドポイントを維持（404挙動含む）。
2. `monitor_status` の値域（`active|reconnecting|degraded`）と数値変換を維持。
3. 例外時は `reconnecting` を経由し、上限超過で `failed` + `degraded` に遷移させる。
4. env fatal 時は run loop 前に `run_progress.json` へ `failed` を出して終了する。
5. 終了時は `shutdown_signal` / `runtime_exception` を区別して進捗へ反映する。

## 完了条件
- `pytest -q tests/test_live_monitor_contract.py tests/test_live_reconnect_policy.py tests/test_live_progress_contract.py tests/test_metrics_contract.py tests/test_runtime_env_validation.py` が通る。

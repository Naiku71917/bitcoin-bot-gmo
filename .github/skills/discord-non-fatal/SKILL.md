# Skill: discord-non-fatal

## 目的
Discord通知処理を変更しても、通知失敗がパイプライン失敗に波及しない非致命契約を守る。

## 前提（必須）
- このSkill適用時は Serena MCP で `telemetry/discord.py` と `telemetry/reporters.py`、関連テストを先に確認する。

## 使うタイミング
- `send_discord_webhook()` の送信処理を変更する時
- webhook環境変数名やpayload形式を変更する時
- 通知結果の `status` / `reason` の扱いを変更する時

## 主な編集対象
- `src/bitcoin_bot/telemetry/discord.py`
- `src/bitcoin_bot/telemetry/reporters.py`（通知結果をrun_completeへ載せる場合）
- `tests/test_discord_non_fatal.py`
- `tests/test_main_contract.py`（run_complete契約に影響する場合）

## 実行手順
1. `enabled=False` は `disabled` を返す既存挙動を維持。
2. URL未設定や送信失敗時は例外を外に投げず `failed` + `reason` を返す。
3. `emit_run_complete()` 経由で通知結果が `notifications.discord` に残ることを確認。
4. `validate_runtime_environment()` の warning（`discord_webhook_missing`）との整合を維持。
5. 新しい失敗パターン追加時は失敗テストを先に追加。

## 完了条件
- 通知失敗時も run 全体が継続する。
- `pytest -q tests/test_discord_non_fatal.py tests/test_main_contract.py tests/test_runtime_env_validation.py` が通る。

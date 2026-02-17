# AGENTS.md

このリポジトリで作業するAIエージェント向けの実行ガイドです。

## 読み順（必須）
1. `.github/copilot-instructions.md`
2. この `AGENTS.md`
3. 目的に合う Skill（`.github/skills/*/SKILL.md`）

## まず守るべき固定契約
- `main.run` の固定フローを壊さない:
  - `load_runtime_config` -> `validate_config` -> mode runner -> `emit_run_complete`
- run完了時の契約を維持する:
  - `var/artifacts/run_complete.json` を atomic write
  - STDOUT に `BEGIN_RUN_COMPLETE_JSON` / `END_RUN_COMPLETE_JSON`
- Discord通知は非致命（失敗でプロセスを落とさない）

## 作業の進め方（標準）
- 変更前に、影響範囲のテストファイルを同時に特定する（例: `tests/test_main_contract.py`）。
- 変更は最小単位で行い、既存の責務分離（`config`/`pipeline`/`telemetry`/`exchange`）を崩さない。
- 実装後は以下を優先順で確認:
  - `pytest -q`
  - `pre-commit run --all-files`

## Skillの選び方
- run完了ペイロード・通知・出力契約を触る: `run-complete-contract`
- YAMLモデルやバリデーションを触る: `config-validation`
- mode分岐やrunner挙動を触る: `pipeline-mode-changes`
- 取引所抽象やadapterを触る: `exchange-protocol`
- OHLCV検証ロジックを触る: `ohlcv-contract`
- Discord通知の非致命挙動を触る: `discord-non-fatal`
- CI一致の確認や品質チェック: `quality-gates`

## 変更時の基本対応表
- Main/契約: `src/bitcoin_bot/main.py`, `src/bitcoin_bot/telemetry/reporters.py`, `tests/test_main_contract.py`
- Config: `src/bitcoin_bot/config/{models,loader,validator}.py`, `tests/test_config_validation.py`
- Exchange: `src/bitcoin_bot/exchange/{protocol,gmo_adapter}.py`, `tests/test_exchange_protocol.py`
- OHLCV: `src/bitcoin_bot/data/ohlcv.py`, `tests/test_ohlcv_contract.py`
- Discord: `src/bitcoin_bot/telemetry/discord.py`, `tests/test_discord_non_fatal.py`

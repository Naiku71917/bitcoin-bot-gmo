# AGENTS.md

このリポジトリで作業するAIエージェント向けの実行ガイドです。

## 読み順（必須）
1. `.github/copilot-instructions.md`
2. `.github/serena-instructions.md`
3. この `AGENTS.md`
4. 目的に合う Skill（`.github/skills/*/SKILL.md`）

## Serena MCP の基本方針
- **全作業で Serena MCP を必ず利用**し、対象コード理解を Serena 経由で行う。
- セッション開始時は Serena のオンボーディング状態を確認し、未実施なら先に実施する。
- Serena が使えない場合は、その旨を明示したうえでユーザー確認後に最小仮説で進める。
- 詳細手順は `.github/serena-instructions.md` に従う。

## まず守るべき固定契約
- `main.run` の固定フローを壊さない:
  - `load_runtime_config` -> `validate_config` -> mode runner -> `emit_run_complete`
- run完了時の契約を維持する:
  - `var/artifacts/run_complete.json` を atomic write
  - STDOUT に `BEGIN_RUN_COMPLETE_JSON` / `END_RUN_COMPLETE_JSON`
- live実行時の進捗契約を維持する:
  - `var/artifacts/run_progress.json` を更新
  - `monitor_status`, `reconnect_count` を保持
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
- 戦略出力や指標列契約を触る: `strategy-indicator-contract`
- 最適化スコア/ゲート/リスクガードを触る: `optimizer-risk-contract`
- `scripts/run_live.py` の運用監視・再接続・metricsを触る: `live-runtime-ops`
- CI一致の確認や品質チェック: `quality-gates`

## 変更時の基本対応表
- Main/契約: `src/bitcoin_bot/main.py`, `src/bitcoin_bot/telemetry/reporters.py`, `tests/test_main_contract.py`
- Config: `src/bitcoin_bot/config/{models,loader,validator}.py`, `tests/test_config_validation.py`
- Exchange: `src/bitcoin_bot/exchange/{protocol,gmo_adapter}.py`, `tests/test_exchange_protocol.py`
- Strategy/Indicators: `src/bitcoin_bot/{strategy/core.py,indicators/generator.py}`, `tests/test_strategy_contract.py`, `tests/test_indicator_contract.py`
- Optimizer/Risk: `src/bitcoin_bot/optimizer/{orchestrator,gates}.py`, `tests/test_optimizer_contract.py`, `tests/test_risk_guards.py`, `tests/test_backtest_metrics_contract.py`
- Live Ops: `scripts/run_live.py`, `tests/test_live_monitor_contract.py`, `tests/test_live_reconnect_policy.py`, `tests/test_metrics_contract.py`, `tests/test_runtime_env_validation.py`
- OHLCV: `src/bitcoin_bot/data/ohlcv.py`, `tests/test_ohlcv_contract.py`
- Discord: `src/bitcoin_bot/telemetry/discord.py`, `tests/test_discord_non_fatal.py`

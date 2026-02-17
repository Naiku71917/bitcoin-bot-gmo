# Copilot 指示書（`bitcoin-bot-gmo`）

## プロジェクトの目的と境界
- このリポジトリは、GMOコイン向けBTCボット（現物/レバ）の **Python 3.12スケルトン**。
- 実装は最小・契約先行で進め、推測ベースの機能追加はしない。
- `src/bitcoin_bot/` の現在のレイアウトと責務分離を維持する。

## エージェント向け参照順
- まず `AGENTS.md` を読む（作業ルールとSkill選択の入口）。
- **全作業で Serena MCP を必ず使い**、`.github/instructions/serena-instructions.md` を先に確認する。
- Skillを新規作成/更新する場合は `.github/skills/SKILL_FORMAT.md` に従う。
- 次に変更内容に応じた Skill を読む:
  - `.github/skills/run-complete-contract/SKILL.md`
  - `.github/skills/config-validation/SKILL.md`
  - `.github/skills/pipeline-mode-changes/SKILL.md`
  - `.github/skills/exchange-protocol/SKILL.md`
  - `.github/skills/ohlcv-contract/SKILL.md`
  - `.github/skills/discord-non-fatal/SKILL.md`
  - `.github/skills/strategy-indicator-contract/SKILL.md`
  - `.github/skills/optimizer-risk-contract/SKILL.md`
  - `.github/skills/live-runtime-ops/SKILL.md`
  - `.github/skills/quality-gates/SKILL.md`

## 全体像（最初に読む）
- エントリ: `src/bitcoin_bot/main.py`
  - 固定フロー: `load_runtime_config` -> `validate_config` -> mode別runner -> `emit_run_complete`
- Runner群: `src/bitcoin_bot/pipeline/{backtest_runner,paper_runner,live_runner}.py`
  - `main.run()` は `runtime.mode`（`backtest|paper|live`）で分岐する。
- 契約/テレメトリ: `src/bitcoin_bot/telemetry/reporters.py`, `src/bitcoin_bot/utils/io.py`
  - `emit_run_complete()` が最終ペイロードを組み立て、`run_complete.json` を原子的に保存する。

## 非交渉の契約
- run完了契約は必ず維持する:
  - `atomic_dump_json` で `var/artifacts/run_complete.json` を出力。
  - 標準出力に `BEGIN_RUN_COMPLETE_JSON` と `END_RUN_COMPLETE_JSON` を出す。
- live進捗契約は必ず維持する:
  - `emit_run_progress()` で `var/artifacts/run_progress.json` を更新。
  - `monitor_status`（`active|reconnecting|degraded`）と `reconnect_count` を保持。
- Discord通知は **非致命**:
  - `send_discord_webhook()` は status/reason を返し、失敗してもパイプラインを落とさない。
- 設定バリデーションは fail-fast + 正規化:
  - `runtime.mode` は `{backtest,paper,live}`。
  - `runtime.execute_orders` は bool。
  - `exchange.product_type` は `{spot,leverage}`。
  - `optimizer.opt_trials` は `1..500` にクランプ。

## 開発ワークフロー（正）
- セットアップ: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]`
- ローカル実行:
  - `python -m bitcoin_bot.main --config configs/runtime.example.yaml --mode backtest`
  - `python -m bitcoin_bot.main --config configs/runtime.live.spot.yaml --mode live`
- 品質ゲート（CIと一致）:
  - `pre-commit run --all-files`
  - `pytest -q`
- コンテナ運用:
  - `docker compose up -d`（`run_live` が書く `var/artifacts/heartbeat.txt` をhealthcheckで監視）

## Skill利用の指針
- Serena MCP での調査・読取手順は `.github/instructions/serena-instructions.md` を基準にする。
- run完了ペイロードや通知仕様を変更する場合は `run-complete-contract` を適用。
- 設定項目の追加・制約変更は `config-validation` を適用。
- mode分岐やrunner変更は `pipeline-mode-changes` を適用。
- 取引所抽象やGMO adapter変更は `exchange-protocol` を適用。
- OHLCVデータ契約の変更は `ohlcv-contract` を適用。
- Discord通知の失敗ハンドリング変更は `discord-non-fatal` を適用。
- 戦略出力や指標カラム契約の変更は `strategy-indicator-contract` を適用。
- 最適化スコア・ゲート・リスクガード変更は `optimizer-risk-contract` を適用。
- デーモン再接続・`/healthz`/`/metrics`・環境検証変更は `live-runtime-ops` を適用。
- 仕上げ検証は `quality-gates` を適用し、CIと同コマンドで確認する。

## このプロジェクト特有の実装パターン
- 設定モデル/正規化モデルは `dataclass(slots=True)` を使う（`config/models.py`, `exchange/protocol.py`）。
- 取引所アクセスは `ExchangeProtocol` 境界の内側に閉じ、上位層へGMO固有仕様を漏らさない。
- 生成物は `var/`（`artifacts`/`logs`/`cache`）に集約し、バリデーション経路で作成する。
- runner/reporter と同様に、小さな純関数 + dict契約を優先する。

## 挙動変更時に同時更新するファイル
- メインフロー/出力契約: `main.py`, `telemetry/reporters.py`, `tests/test_main_contract.py`
- 設定スキーマ/検証: `config/models.py`, `config/loader.py`, `config/validator.py`, `tests/test_config_validation.py`
- 取引所抽象: `exchange/protocol.py`, `exchange/gmo_adapter.py`, `tests/test_exchange_protocol.py`
- Strategy/Indicators: `strategy/core.py`, `indicators/generator.py`, `tests/test_strategy_contract.py`, `tests/test_indicator_contract.py`
- Optimizer/Risk: `optimizer/orchestrator.py`, `optimizer/gates.py`, `tests/test_optimizer_contract.py`, `tests/test_risk_guards.py`
- Live Ops: `scripts/run_live.py`, `tests/test_live_monitor_contract.py`, `tests/test_live_reconnect_policy.py`, `tests/test_metrics_contract.py`, `tests/test_runtime_env_validation.py`
- OHLCV契約: `data/ohlcv.py`, `tests/test_ohlcv_contract.py`
- Discord挙動: `telemetry/discord.py`, `tests/test_discord_non_fatal.py`

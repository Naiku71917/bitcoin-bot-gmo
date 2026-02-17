# Copilot実運用ガイド（GMO新規ボット）

この文書は、テンプレート集ではなく、**そのまま実務で使う手順書**です。
目的は「Copilot Chat 主導でも、仕様逸脱なく短いサイクルで実装を完了すること」です。

---

## 0. 使い方（最初に読む）

運用ルール:
- 1タスク = 1プロンプト = 1PR
- 1PRは 300〜600行変更を目安（巨大PR禁止）
- すべてのPRで「受け入れ条件」を固定記載
- 契約破壊禁止:
  - `run_complete.json` 出力
  - `BEGIN_RUN_COMPLETE_JSON` / `END_RUN_COMPLETE_JSON`
  - Discord失敗時は非致命

最初に参照する仕様:
- [docs/spec.md](docs/spec.md)
- [docs/initial_skeleton.md](docs/initial_skeleton.md)

---

## 1. 実行フロー（Day1〜Day3）

### Day1: 骨組みと契約
1. リポジトリ初期化
2. 設定モデル + バリデータ
3. `run_complete` 契約
4. 最小テスト通過

### Day2: 交換所とデータ
1. exchange protocol + GMO adapter（spot/leverage）
2. OHLCV 契約
3. Discord 非致命通知
4. テスト追加

### Day3: 品質・運用
1. `.pre-commit-config.yaml`
2. coverage 設定
3. Docker常駐最小構成
4. CIコマンド固定

---

## 2. Copilotに貼る「実運用プロンプト」

以下はテンプレートではなく、実際にこの順で使う前提の文面です。

## 2.1 PR-01: 初期スケルトン作成

```text
あなたはPythonアーキテクトです。新規リポジトリの初期スケルトンを実装してください。

要件:
- Python 3.12
- srcレイアウト
- 作成対象
  - pyproject.toml
  - README.md
  - .gitignore
  - .editorconfig
  - .env.example
  - Dockerfile
  - docker-compose.yml
  - src/bitcoin_bot/*
  - configs/
  - scripts/
  - tests/
  - var/artifacts, var/logs

制約:
- 不要なダミー処理は追加しない
- main.run で mode 分岐できる土台を作る
- 将来拡張可能な責務分離にする

受け入れ条件:
- ファイル構成が docs/initial_skeleton.md と一致
- pytest -q が最低1本以上実行できる状態

出力:
- 変更ファイル一覧
- 未実装項目
```

## 2.2 PR-02: 設定モデル + バリデータ

```text
RuntimeConfig の最小実装を追加してください。

対象:
- src/bitcoin_bot/config/models.py
- src/bitcoin_bot/config/loader.py
- src/bitcoin_bot/config/validator.py
- tests/test_config_validation.py

必須仕様:
- runtime.mode: backtest|paper|live
- exchange.product_type: spot|leverage
- optimizer.opt_trials: 1..500 にクランプ
- paths.* は作成可能であること

受け入れ条件:
- 無効modeでfail-fast
- 無効product_typeでfail-fast
- opt_trialsクランプのテストが通る
```

## 2.3 PR-03: run_complete 契約

```text
run_complete 契約を実装してください。

対象:
- src/bitcoin_bot/utils/io.py
- src/bitcoin_bot/telemetry/reporters.py
- src/bitcoin_bot/main.py
- tests/test_main_contract.py

必須仕様:
- run終了時に var/artifacts/run_complete.json を atomic write
- STDOUTに BEGIN_RUN_COMPLETE_JSON と END_RUN_COMPLETE_JSON を出力
- notifications.discord.status/reason を保持可能

受け入れ条件:
- run_complete.json の必須キー存在
- マーカー出力テスト通過
```

## 2.4 PR-04: Exchange Protocol + GMO Adapter

```text
取引所抽象と GMO adapter を実装してください。

対象:
- src/bitcoin_bot/exchange/protocol.py
- src/bitcoin_bot/exchange/gmo_adapter.py
- tests/test_exchange_protocol.py

必須メソッド:
- fetch_klines
- fetch_balances
- fetch_positions
- place_order
- cancel_order
- fetch_order

必須仕様:
- spot/leverage 切替対応
- 上位層へは正規化モデルで返す

受け入れ条件:
- protocol準拠テスト通過
- spot/leverage 切替テスト通過
```

## 2.5 PR-05: OHLCV 契約

```text
OHLCV正規化を実装してください。

対象:
- src/bitcoin_bot/data/ohlcv.py
- tests/test_ohlcv_contract.py

必須仕様:
- columns: [timestamp, open, high, low, close, volume]
- UTC index
- attrs: provider, symbol, timeframe
- 欠損処理方針を明示

受け入れ条件:
- 列順/UTC/attrs テスト通過
```

## 2.6 PR-06: Discord 非致命通知

```text
Discord通知を非致命設計で実装してください。

対象:
- src/bitcoin_bot/telemetry/discord.py
- tests/test_discord_non_fatal.py

必須仕様:
- 送信失敗で run 全体を落とさない
- notifications.discord.status = failed
- notifications.discord.reason を保存

受け入れ条件:
- HTTP失敗モックで非致命テスト通過
```

## 2.7 PR-07: pre-commit + coverage

```text
品質ゲートを追加してください。

対象:
- .pre-commit-config.yaml
- pyproject.toml
- README.md

必須仕様:
- pre-commit hooks: ruff, ruff-format, mypy, end-of-file-fixer, trailing-whitespace, check-merge-conflict
- coverage:
  - tool.coverage.run.branch = true
  - tool.coverage.run.source = ["src/bitcoin_bot"]
  - tool.coverage.report.fail_under = 70
  - XML/HTML出力先を var/artifacts/coverage に固定

受け入れ条件:
- pre-commit run --all-files が通る
- pytest -q --cov=src/bitcoin_bot --cov-report=term-missing --cov-report=xml --cov-report=html が通る
```

## 2.8 PR-08: Docker 常駐最小構成

```text
Docker常駐の最小構成を実装してください。

対象:
- docker-compose.yml
- scripts/run_live.py

必須仕様:
- restart: unless-stopped
- healthcheck (/healthz)
- ./var:/app/var マウント
- logging max-size/max-file
- graceful shutdown

受け入れ条件:
- docker compose up -d で起動
- healthcheck が healthy になる
```

## 2.9 PR-09: Exchangeストリーム契約の拡張

```text
Exchange Protocol / GMO Adapter を、仕様書準拠の不足分まで拡張してください。

対象:
- src/bitcoin_bot/exchange/protocol.py
- src/bitcoin_bot/exchange/gmo_adapter.py
- tests/test_exchange_protocol.py

必須仕様:
- protocol に以下を追加
  - fetch_ticker
  - stream_order_events
  - stream_account_events
- 既存の spot/leverage 切替と整合を保つ
- 上位層へ返す戻り値の契約を明示（dict/dataclass のどちらかで統一）

受け入れ条件:
- 既存テストを壊さない
- 追加メソッド分の契約テストが通る
```

## 2.10 PR-10: 指標生成（EMA/RSI/ATR + feature flags）

```text
指標生成モジュールを仕様準拠で実装してください。

対象:
- src/bitcoin_bot/indicators/generator.py
- tests/test_indicator_contract.py（新規可）

必須仕様:
- EMA（短期/長期）, RSI, ATR を生成
- 既存カラムを上書きしない
- 設定で計算窓を切替可能
- feature flags: slope_norm, gap_norm をON/OFF可能

受け入れ条件:
- 指標列の存在・命名規則テスト通過
- flags OFF 時に追加列が出ないことを確認
```

## 2.11 PR-11: Strategy意思決定契約

```text
戦略コアの意思決定出力を契約先行で実装してください。

対象:
- src/bitcoin_bot/strategy/core.py
- tests/test_strategy_contract.py（新規可）

必須仕様:
- 出力契約:
  - action: buy|sell|hold
  - confidence: 0.0..1.0
  - reason_codes: list[str]
  - risk: sl, tp, max_holding_bars
- 判定は最小実装でよいが、EMA/RSI/ATR を入力として扱える構造にする
- クールダウンや最小信頼度フィルタのフックを用意

受け入れ条件:
- 出力スキーマ検証テスト通過
- 境界値（confidence 0/1, hold判定）テスト通過
```

## 2.12 PR-12: リスクガード（degraded/abort）

```text
リスク管理の最低限ガードを追加してください。

対象:
- src/bitcoin_bot/pipeline/live_runner.py
- src/bitcoin_bot/optimizer/gates.py
- tests/test_risk_guards.py（新規可）

必須仕様:
- 最大ドローダウン、日次損失上限、建玉サイズ上限の最低3ガード
- 閾値超過時に degraded または abort を返す
- 停止理由コードを run サマリへ受け渡せる形にする

受け入れ条件:
- 閾値超過ケースのテスト通過
- 停止理由が欠落しないことを確認
```

## 2.13 PR-13: 最適化スコア/ゲート/サルベージ

```text
最適化出力契約を仕様どおりに実装してください。

対象:
- src/bitcoin_bot/optimizer/orchestrator.py
- src/bitcoin_bot/optimizer/gates.py
- src/bitcoin_bot/telemetry/reporters.py
- tests/test_optimizer_contract.py（新規可）

必須仕様:
- run_complete の optimization に以下を必ず含める
  - score
  - gates.accept
  - salvage
- gate判定の理由コードを保持
- opt_trials の実行値をサマリへ記録

受け入れ条件:
- optimization 契約テスト通過
- run_complete の必須キーを壊さない
```

## 2.14 PR-14: 常駐進捗・監視出力（run_progress）

```text
常駐運用向けの進捗出力を追加してください。

対象:
- src/bitcoin_bot/pipeline/live_runner.py
- src/bitcoin_bot/telemetry/reporters.py
- scripts/run_live.py
- tests/test_live_progress_contract.py（新規可）

必須仕様:
- var/artifacts/run_progress.json を定期更新
- 原子的書き込みを使う（既存ioユーティリティを優先）
- 少なくとも status, updated_at, mode, last_error を保持
- 例外時も最終状態を degraded/failed で保存

受け入れ条件:
- run_progress.json が生成・更新される
- 既存の run_complete 契約を壊さない
```

## 2.15 PR-15: CI一致の統合検証

```text
ここまでの変更をCI相当で検証し、必要最小限の修正のみ行ってください。

対象:
- README.md
- tests/（不足テストの補完のみ）

実行コマンド:
- pre-commit run --all-files
- pytest -q
- pytest -q --cov=src/bitcoin_bot --cov-report=term-missing --cov-report=xml --cov-report=html

受け入れ条件:
- すべての品質ゲートを通過
- 契約（run_complete/marker/Discord非致命）を維持
```

## 2.16 PR-16: Backtest結果メトリクス契約

```text
Backtest runner を、評価指標の最小契約まで実装してください。

対象:
- src/bitcoin_bot/pipeline/backtest_runner.py
- src/bitcoin_bot/optimizer/orchestrator.py
- tests/test_backtest_metrics_contract.py（新規可）

必須仕様:
- backtest summary に最低限以下を保持
  - return
  - max_drawdown
  - win_rate
  - profit_factor
  - trade_count
- optimization.score に backtest 指標を使った最小スコアを反映
- 既存 run_complete 契約を壊さない

受け入れ条件:
- backtest メトリクス契約テスト通過
- run_complete の optimization.score が欠落しない
```

## 2.17 PR-17: Paperモード最小実運用化

```text
Paper runner を、注文擬似実行の最低限契約まで実装してください。

対象:
- src/bitcoin_bot/pipeline/paper_runner.py
- src/bitcoin_bot/strategy/core.py
- tests/test_paper_runner_contract.py（新規可）

必須仕様:
- strategy decision を受けて paper 注文イベントを生成
- summary に以下を保持
  - action
  - confidence
  - order_count
  - reason_codes
- hold 判定時は注文を発行しない

受け入れ条件:
- hold / buy / sell の分岐テスト通過
- summary 契約テスト通過
```

## 2.18 PR-18: Exchangeエラー正規化と再試行方針

```text
GMO adapter の失敗系を仕様どおり正規化してください。

対象:
- src/bitcoin_bot/exchange/protocol.py
- src/bitcoin_bot/exchange/gmo_adapter.py
- tests/test_exchange_error_normalization.py（新規可）

必須仕様:
- NormalizedError を実際に返せる経路を追加
- category を最低限以下で分類
  - auth
  - rate_limit
  - validation
  - network
  - exchange
- retryable 判定を保持

受け入れ条件:
- 代表的な失敗ケースの正規化テスト通過
- 既存の spot/leverage 契約テストを壊さない
```

## 2.19 PR-19: リスクガード拡張（不足3項目）

```text
既存のリスクガードに不足項目を追加してください。

対象:
- src/bitcoin_bot/optimizer/gates.py
- src/bitcoin_bot/pipeline/live_runner.py
- tests/test_risk_guards.py

必須仕様:
- 既存3ガードに加えて以下を追加
  - 1トレードあたり許容損失
  - レバレッジ上限
  - wallet drift
- 閾値超過時は degraded または abort を返し、reason_codes を保持
- run サマリへ停止理由が欠落しない

受け入れ条件:
- 追加3ガードの閾値超過テスト通過
- 既存ガードテストを壊さない
```

## 2.20 PR-20: ライブ監視メトリクス契約

```text
常駐運用の監視メトリクスを run_progress/run_complete 契約へ追加してください。

対象:
- src/bitcoin_bot/telemetry/reporters.py
- src/bitcoin_bot/pipeline/live_runner.py
- scripts/run_live.py
- tests/test_live_monitor_contract.py（新規可）

必須仕様:
- monitor status を保持
  - active
  - reconnecting
  - degraded
- run_progress に monitor 関連フィールドを追加
- run_complete の pipeline_summary に監視要約を残す

受け入れ条件:
- monitor status 遷移テスト通過
- run_complete / marker 契約を壊さない
```

## 2.21 PR-21: 運用ドキュメント更新（Runbook最小）

```text
現行実装に合わせて運用ドキュメントを最小更新してください。

対象:
- docs/architecture.md
- docs/operations.md
- README.md

必須仕様:
- 現在の run_progress / run_complete / healthcheck 実装と一致
- 日常運用コマンド（起動/停止/確認）を明記
- 障害時の一次切り分け（ログ, artifacts, health）を短く記載

受け入れ条件:
- 記載内容が実装と矛盾しない
- pre-commit / pytest が通る
```

## 2.22 PR-22: GMO実通信の最小実装（Read Only）

```text
GMO adapter を read-only API まで実運用可能な最小実装へ更新してください。

対象:
- src/bitcoin_bot/exchange/gmo_adapter.py
- src/bitcoin_bot/exchange/protocol.py（必要最小限）
- tests/test_exchange_runtime_integration.py（新規可）

必須仕様:
- 少なくとも以下を実通信化（HTTP）
  - fetch_ticker
  - fetch_balances（認証あり）
- タイムアウト/通信失敗時は NormalizedError へ正規化
- 現物/レバで product_type の整合を保つ

実行コマンド（必須）:
- pytest -q tests/test_exchange_runtime_integration.py
- pre-commit run --all-files

受け入れ条件:
- 通信成功モック/失敗モックの両方で契約テスト通過
- 既存 exchange 契約テストを壊さない
```

## 2.23 PR-23: ライブ再接続ポリシーの実装

```text
run_live 常駐ループに再接続ポリシーを実装し、monitor status を実挙動と一致させてください。

対象:
- scripts/run_live.py
- src/bitcoin_bot/telemetry/reporters.py
- tests/test_live_reconnect_policy.py（新規可）

必須仕様:
- 例外発生時、即終了ではなく再試行ループ（回数/待機秒は環境変数で制御）
- monitor status 遷移
  - active -> reconnecting -> active/degraded
- 再試行上限超過時に failed で終了

実行コマンド（必須）:
- pytest -q tests/test_live_reconnect_policy.py
- pytest -q

受け入れ条件:
- 再接続成功/失敗の遷移テスト通過
- run_progress / run_complete 契約を壊さない
```

## 2.24 PR-24: Prometheus最小エンドポイント追加

```text
監視の三層要件を満たすため、Prometheus メトリクスの最小実装を追加してください。

対象:
- scripts/run_live.py
- src/bitcoin_bot/telemetry/reporters.py（必要最小限）
- docker-compose.yml
- tests/test_metrics_contract.py（新規可）

必須仕様:
- /metrics エンドポイントを追加（カウンタ/ゲージを最低3種）
  - run_loop_total
  - run_loop_failures_total
  - monitor_status（ラベルまたは数値）
- 既存 /healthz と共存

実行コマンド（必須）:
- docker-compose up -d --build
- curl -fsS http://127.0.0.1:9754/metrics
- pytest -q tests/test_metrics_contract.py

受け入れ条件:
- /metrics が取得できる
- monitor status がメトリクスに反映される
```

## 2.25 PR-25: 実行保護フラグ（本番誤発注防止）

```text
本番誤発注を防ぐため、注文実行可否フラグを導入してください。

対象:
- src/bitcoin_bot/config/models.py
- src/bitcoin_bot/config/loader.py
- src/bitcoin_bot/config/validator.py
- src/bitcoin_bot/pipeline/live_runner.py
- tests/test_execute_orders_flag.py（新規可）

必須仕様:
- `runtime.execute_orders`（bool, default false）を追加
- false の場合は注文系を実行せず、reason_codes に `execute_orders_disabled`
- run_summary に実行可否を明示

実行コマンド（必須）:
- pytest -q tests/test_execute_orders_flag.py
- pytest -q

受け入れ条件:
- false で注文未実行が保証される
- true で既存フローに影響しない
```

## 2.26 PR-26: Secrets/環境変数の起動前検証

```text
運用事故防止のため、起動前に secrets/環境変数の最小検証を追加してください。

対象:
- scripts/run_live.py
- src/bitcoin_bot/config/validator.py（必要最小限）
- README.md
- tests/test_runtime_env_validation.py（新規可）

必須仕様:
- live + execute_orders=true のとき、必須環境変数未設定なら起動失敗
- Discord有効時の webhook 設定不備は非致命（警告+status failed）
- 検証結果を run_progress へ残す

実行コマンド（必須）:
- pytest -q tests/test_runtime_env_validation.py
- pre-commit run --all-files

受け入れ条件:
- 必須環境変数不足ケースをテストで検出
- 非致命通知契約を壊さない
```

## 2.27 PR-27: 24h運用スモーク用スクリプト追加

```text
実運用前確認として、長時間運用のスモーク検証スクリプトを追加してください。

対象:
- scripts/smoke_live_daemon.sh（新規）
- docs/operations.md

必須仕様:
- 以下を自動実行
  - 起動
  - health 監視
  - run_progress/run_complete の存在確認
  - 異常時にログ収集して終了コード非0
- 既存コードへの変更は最小化

実行コマンド（必須）:
- bash scripts/smoke_live_daemon.sh

受け入れ条件:
- 正常系で終了コード0
- 異常系で終了コード非0 + 切り分け情報出力
```

---

## 3. PRレビュー時のチェックリスト

全PR共通:
- 仕様逸脱なし（本書 + 仕様書）
- 契約破壊なし（run_complete + marker + Discord非致命）
- 変更理由がPR本文に記載済み
- テストログが添付済み

品質ゲート:
- `ruff check .`
- `mypy src`
- `pytest -q`
- `pre-commit run --all-files`
- coverage コマンド

---

## 4. 失敗したときの再指示文

Copilot の実装が要件を満たさない場合、次を貼る:

```text
前回実装は受け入れ条件を満たしていません。差分修正のみ実施してください。

不足点:
- <不足1>
- <不足2>

制約:
- 既存の通過テストを壊さない
- 変更範囲を最小化

完了条件:
- 失敗したテストが全て通る
- 契約（run_complete/marker/Discord非致命）を維持
```

---

## 5. 運用で守る禁止事項

- 既存実装のコピペ移植
- 一度に大規模PR（1000行超）
- 受け入れ条件なしの実装依頼
- テスト未実行のままマージ

---

## 6. 最終ゴール判定

以下が満たされたら、初期実装完了:
- PR-01〜PR-08 がすべて完了
- `run_complete` 契約テストが安定
- spot/leverage の adapter テスト通過
- pre-commit + coverage + Docker 起動確認済み

以後は戦略・最適化・ライブ監視の拡張フェーズへ進む。

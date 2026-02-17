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

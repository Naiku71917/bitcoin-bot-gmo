# 新規リポジトリ初期スケルトン仕様（GMOコイン版）

本書は、別ワークスペースでゼロから実装するための**初期スケルトン定義**です。
対象は以下の3点です。

1. フォルダ構成
2. 設定スキーマ（最小）
3. 最小テスト（契約テスト）
4. `.pre-commit-config.yaml` 設定
5. coverage 設定

---

## 1. 目的

- 実装初期で迷わない最小構成を固定する
- `run_complete` 契約を最初に成立させる
- GMOコインの現物/レバ両対応を前提に、exchange差分を抽象化する
- Docker常駐運用に必要な構造を最初から含める

---

## 2. 初期フォルダ構成（推奨）

```text
bitcoin-bot-gmo/
├── README.md
├── pyproject.toml
├── .gitignore
├── .editorconfig
├── .env.example
├── .pre-commit-config.yaml
├── docker-compose.yml
├── Dockerfile
├── configs/
│   ├── runtime.example.yaml
│   ├── runtime.live.spot.yaml
│   └── runtime.live.leverage.yaml
├── docs/
│   ├── architecture.md
│   ├── operations.md
│   ├── api_contracts.md
│   └── run_complete_schema.md
├── scripts/
│   ├── run_backtest.py
│   └── run_live.py
├── src/bitcoin_bot/
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── models.py
│   │   └── validator.py
│   ├── exchange/
│   │   ├── __init__.py
│   │   ├── protocol.py
│   │   └── gmo_adapter.py
│   ├── data/
│   │   ├── __init__.py
│   │   └── ohlcv.py
│   ├── indicators/
│   │   ├── __init__.py
│   │   └── generator.py
│   ├── strategy/
│   │   ├── __init__.py
│   │   └── core.py
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── orchestrator.py
│   │   └── gates.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── backtest_runner.py
│   │   ├── paper_runner.py
│   │   └── live_runner.py
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── reporters.py
│   │   └── discord.py
│   └── utils/
│       ├── __init__.py
│       ├── io.py
│       └── logging.py
├── tests/
│   ├── conftest.py
│   ├── test_main_contract.py
│   ├── test_config_validation.py
│   ├── test_exchange_protocol.py
│   ├── test_ohlcv_contract.py
│   └── test_discord_non_fatal.py
└── var/
    ├── artifacts/
    └── logs/
```

### 2.1 設計ルール

- `exchange` は必ず `protocol.py` を介して利用（直結禁止）
- `pipeline` 以外から `main.py` へ依存しない
- `telemetry.reporters.emit_run_complete` は全モード終了時に必ず呼ぶ
- 生成物は `var/` 配下へ集約

---

## 3. 設定スキーマ（最小）

## 3.1 YAML例（`configs/runtime.example.yaml`）

```yaml
runtime:
  mode: live            # backtest | paper | live
  profile: default
  interval_seconds: 300

exchange:
  name: gmo
  product_type: spot    # spot | leverage
  symbol: BTC_JPY
  api_base_url: "https://api.coin.z.com"
  ws_url: "wss://api.coin.z.com/ws"

data:
  timeframe: "1m"
  source_priority: ["api", "csv"]
  csv_path: "./data/sample_klines.csv"

strategy:
  min_confidence: 0.55
  ema_fast: 12
  ema_slow: 26
  rsi_period: 14
  atr_period: 14
  feature_flags:
    slope_norm: true
    gap_norm: true

risk:
  max_drawdown: 0.20
  daily_loss_limit: 0.05
  max_position_size: 0.10
  max_leverage: 2.0

optimizer:
  enabled: true
  opt_trials: 50         # clamp: 1..500

notify:
  discord:
    enabled: true
    webhook_env: DISCORD_WEBHOOK_URL

observability:
  prometheus_enabled: true
  prometheus_port: 9752
  health_port: 9754

paths:
  artifacts_dir: "./var/artifacts"
  logs_dir: "./var/logs"
  cache_dir: "./var/cache"
```

## 3.2 モデル最小要件

- `RuntimeConfig`
  - `runtime`, `exchange`, `data`, `strategy`, `risk`, `optimizer`, `notify`, `observability`, `paths`
- `validate_config` で最低限チェック
  - `mode` が許容値
  - `product_type` が `spot|leverage`
  - `opt_trials` は 1..500 にクランプ
  - ディレクトリ存在/作成可能

## 3.3 run_complete 最小スキーマ

```json
{
  "run_id": "string",
  "started_at": "ISO8601",
  "completed_at": "ISO8601",
  "pipeline": {
    "mode": "live",
    "status": "success|failed|skipped",
    "summary": {}
  },
  "pipeline_summary": {},
  "optimization": {},
  "notifications": {
    "discord": {
      "status": "sent|failed|disabled",
      "reason": "string|null"
    }
  }
}
```

STDOUT契約（必須）
- `BEGIN_RUN_COMPLETE_JSON`
- run_complete JSON本文
- `END_RUN_COMPLETE_JSON`

## 3.4 `.pre-commit-config.yaml` 最小設定例

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.10
    hooks:
      - id: ruff
        args: ["--fix"]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        additional_dependencies: ["types-PyYAML"]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-merge-conflict
```

必須ルール:
- `pre-commit install` を初回セットアップに含める
- CI で `pre-commit run --all-files` を実行する

## 3.5 coverage 最小設定例（`pyproject.toml`）

```toml
[tool.coverage.run]
branch = true
source = ["src/bitcoin_bot"]
omit = [
  "*/__init__.py",
]

[tool.coverage.report]
show_missing = true
skip_covered = false
fail_under = 70
exclude_lines = [
  "pragma: no cover",
  "if TYPE_CHECKING:",
  "if __name__ == .__main__.:",
]

[tool.coverage.xml]
output = "var/artifacts/coverage/coverage.xml"

[tool.coverage.html]
directory = "var/artifacts/coverage/html"
```

推奨コマンド:
- `pytest -q --cov=src/bitcoin_bot --cov-report=term-missing --cov-report=xml --cov-report=html`
- カバレッジ成果物は `var/artifacts/coverage/` に集約

---

## 4. 最小テストセット（最優先）

## 4.1 `test_main_contract.py`

目的:
- `main.run` が全モードで `run_complete` を生成すること
- BEGIN/ENDマーカーを出力すること

検証:
- `var/artifacts/run_complete.json` が存在
- JSONに必須キーがある
- 標準出力にマーカーがある

## 4.2 `test_config_validation.py`

目的:
- 設定バリデーションが fail-fast すること

検証:
- 無効 `mode` でエラー
- 無効 `product_type` でエラー
- `opt_trials` のクランプ（1未満→1、500超→500）

## 4.3 `test_exchange_protocol.py`

目的:
- adapter が protocol を満たすこと

検証:
- `fetch_klines`, `place_order`, `cancel_order`, `fetch_balances` が呼べる
- spot/leverage 切替で正規化モデルが壊れない

## 4.4 `test_ohlcv_contract.py`

目的:
- データ前処理契約を固定

検証:
- 列順 `[timestamp, open, high, low, close, volume]`
- UTC index
- 欠損処理ルール
- `attrs` に `provider` などが残る

## 4.5 `test_discord_non_fatal.py`

目的:
- 通知失敗が非致命であること

検証:
- Webhook失敗時でも実行ステータスが継続
- `notifications.discord.status == "failed"`
- `reason` が保存される

---

## 5. 実装順序（Copilot向け）

1. `config/models.py` + `config/validator.py`
2. `utils/io.py`（atomic JSON dump）
3. `telemetry/reporters.py`（run_complete出力）
4. `main.py`（mode分岐 + 契約出力）
5. `exchange/protocol.py` + `exchange/gmo_adapter.py`（ダミー実装可）
6. 最小テスト5本を先に通す
7. その後に指標/戦略/最適化を拡張

---

## 6. Docker最小要件（初期）

- `docker-compose.yml` に bot サービス
- `./var:/app/var` マウント
- `healthcheck` (`/healthz`)
- `restart: unless-stopped`
- loggingローテーション（`max-size`, `max-file`）
- secrets/env の外部注入

## 6.1 品質ゲート最小要件（初期）

- pre-commit
  - `pre-commit run --all-files`
- lint/type
  - `ruff check .`
  - `mypy src`
- test/coverage
  - `pytest -q --cov=src/bitcoin_bot --cov-report=term-missing --cov-report=xml --cov-report=html`

---

## 7. Done条件（初期スケルトン版）

- フォルダ構成が本書と一致
- `runtime.example.yaml` が読み込める
- 最小テスト5本がグリーン
- pre-commit が全フック成功
- coverage レポートが出力され、`fail_under` を満たす
- `run_complete` のJSON/STDOUT契約が成立
- Dockerで1回実行と常駐実行が動く

---

## 8. 補足

- 既存リポジトリのコードは移植しない
- 仕様とテスト観点のみ移植
- スキーマ変更時は `run_complete` バージョン管理を行う

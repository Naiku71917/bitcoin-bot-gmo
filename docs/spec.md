# GMOコイン対応 新規ビットコイン自動売買システム 本番仕様書（再構築用）

## 0. この文書の目的

本書は、**現行ワークスペースの知見を仕様として抽出**し、
**別ワークスペースでゼロから実装**するための本番仕様書です。

- 既存コードの流用は禁止（仕様・設計思想のみ参照）
- 実装は GitHub Copilot Chat 主導
- 取引所は GMOコイン
- 現物/レバレッジ両対応
- 運用基盤は Docker 系（systemd 不使用）
- 通知は Discord Webhook

---

## 1. 開発・運用の前提

### 1.1 非機能（先に固定する項目）

- 可用性: 24/7 常駐、無人復旧（再起動ポリシーあり）
- 監視: Health/Prometheus/Discord の三層
- 監査: 意思決定・注文・約定・停止理由を復元可能
- 安全性: 通知失敗は非致命、取引実行失敗は理由付き縮退
- 保全: run 完了サマリを毎回保存、JSON 契約を固定

### 1.2 本番運用での必須成果物

- `var/artifacts/run_complete.json`
- `var/artifacts/run_progress.json`（常駐時の進捗）
- `var/logs/*.log`
- （任意）`var/artifacts/coverage/latest.json`, `history.json`

---

## 2. 全体アーキテクチャ

```text
app/
  config/        # loader + validator + models
  exchange/      # exchange adapter (GMO spot/leverage)
  data/          # OHLCV loader + normalizer
  indicators/    # EMA/RSI/ATR + feature flags
  strategy/      # signal engine + layer/risk rules
  backtest/      # simulator + metrics
  optimizer/     # scoring/gates/salvage
  pipeline/      # backtest/paper/live orchestrator
  telemetry/     # run_complete + metrics + notifications
  runtime/       # daemon loop + graceful shutdown
  scripts/       # entry wrappers
```

### 2.1 実行フロー（契約）

1. `load_runtime_config`
2. `validate_config`
3. `run_backtest` / `run_paper` / `run_live`
4. `emit_run_complete`

**契約（固定）**
- run 終了時は必ず `run_complete.json` を原子的に出力
- STDOUT に以下マーカーを出す
  - `BEGIN_RUN_COMPLETE_JSON`
  - `END_RUN_COMPLETE_JSON`
- 通知失敗時もパイプライン自体は失敗扱いにしない

---

## 3. 交換所抽象（GMO 現物/レバ 両対応）

## 3.1 抽象インターフェース（必須）

- `fetch_klines(symbol, timeframe, start, end, limit)`
- `fetch_ticker(symbol)`
- `fetch_balances(account_type)`
- `fetch_positions(symbol)`
- `place_order(order_request)`
- `cancel_order(order_id)`
- `fetch_order(order_id)`
- `stream_order_events()`
- `stream_account_events()`

## 3.2 正規化モデル（必須）

### 3.2.1 `NormalizedOrder`
- `exchange`
- `product_type` (`spot`/`leverage`)
- `symbol`
- `side` (`buy`/`sell`)
- `order_type` (`market`/`limit`/...)
- `time_in_force`
- `qty`
- `price` (optional)
- `reduce_only` (optional)
- `client_order_id`

### 3.2.2 `NormalizedFill`
- `order_id`
- `fill_qty`
- `fill_price`
- `fee`
- `fee_currency`
- `timestamp`

### 3.2.3 `NormalizedError`
- `category` (`auth`/`rate_limit`/`validation`/`network`/`exchange`)
- `retryable` (bool)
- `source_code` (取引所の元コード)
- `message`

## 3.3 現物/レバ差分の吸収点

- 口座区分
- 注文可能属性（例: reduce-only の有無）
- 建玉・余力の取得方法
- 手数料体系
- 最小数量/最小金額/ステップ

**方針**
- 戦略層は差分を知らない
- 差分は exchange adapter 内で吸収

---

## 4. データ仕様（OHLCV）

## 4.1 必須カラム

`[timestamp, open, high, low, close, volume]`

## 4.2 必須条件

- UTC インデックス
- 型の一貫性（数値化失敗は欠損として扱う）
- 欠損処理方針を固定（drop/ffill など）
- `DataFrame.attrs` 相当で `provider`, `symbol`, `timeframe` を保持

## 4.3 フォールバック

- API ソース失敗時の CSV フォールバックを許容
- ソース優先順位は設定可能にする

---

## 5. 指標生成仕様

## 5.1 必須指標

- EMA（短期/長期）
- RSI
- ATR
- （拡張）`slope_norm`, `gap_norm` feature flag

## 5.2 実装ルール

- 既存カラムは上書きしない
- 指標の計算窓は設定化
- 追加列の命名規則を固定

---

## 6. 戦略アルゴリズム仕様

## 6.1 意思決定出力

- `action`: `buy` / `sell` / `hold`
- `confidence`: 0.0〜1.0
- `reason_codes`: list[str]
- `risk`: `sl`, `tp`, `max_holding_bars`

## 6.2 判定ロジック（推奨）

1. モメンタム判定（EMAギャップ・傾き）
2. 逆張り/過熱判定（RSI）
3. ボラティリティ補正（ATR）
4. フィルタ（最小信頼度・クールダウン・同時建玉数）

## 6.3 レイヤー戦略（推奨）

- `main`: 主戦略
- `hedge`: リスク低減
- `scalp`: 補助（任意）

各レイヤーに以下を持つ:
- `priority`
- `weight`
- `leverage_limit`
- `cooldown_bars`
- `max_concurrent_trades`

---

## 7. リスク管理仕様

## 7.1 必須ガード

- 最大ドローダウン
- 1トレードあたりの許容損失
- 日次損失上限
- 建玉サイズ上限
- レバレッジ上限
- wallet drift（期待残高と実残高乖離）

## 7.2 停止ルール

- 閾値超過で `degraded` または `abort`
- 停止理由を run サマリに必ず記録

---

## 8. 最適化仕様

## 8.1 トライアル管理

- `opt_trials` は 1〜500 にクランプ
- 実際の実行値を run サマリへ記録

## 8.2 評価指標（最低限）

- return
- max_drawdown
- win_rate
- profit_factor
- trade_count

## 8.3 ゲート/サルベージ

- gate: 合格/不合格 + 理由コード
- salvage: 不合格案の救済ルール（限定条件）

出力契約:
- `optimization.score`
- `optimization.gates.accept`
- `optimization.salvage`

---

## 9. テレメトリ/通知仕様

## 9.1 `run_complete.json` の必須トップレベル

- `run_id`
- `pipeline`（mode/status/summary）
- `pipeline_summary`
- `optimization`
- `notifications.discord`
- `started_at`
- `completed_at`

## 9.2 Discord通知

- 送信先: Webhook
- 内容: 実行モード、主要指標、ゲート判定、警告
- 失敗時ポリシー:
  - 例外で落とさない
  - `notifications.discord.status = failed`
  - `notifications.discord.reason` を保存

## 9.3 監視メトリクス

- 実行回数
- 直近 fill rate
- monitor status (`active`/`reconnecting`/`degraded`)
- salvage 発生率

---

## 10. 常駐運用（Docker 前提）

## 10.1 コンテナライフサイクル

- エントリポイントは live daemon
- graceful shutdown 対応
- 停止猶予を設定（`stop_grace_period`）

## 10.2 必須運用要件

- `healthcheck` 実装（`/healthz`）
- `restart: unless-stopped` 相当
- CPU/Memory 制限
- ログローテーション（driver設定）
- 永続ボリューム（`/app/var`）

## 10.3 Secrets

- `.env` 直書き運用は最小化
- Docker/K8s secrets を標準化
- 鍵ローテーション手順を runbook に明記

## 10.4 将来Kubernetes互換

- readiness/liveness/startup probe
- rolling update 前に安全停止フロー
- ConfigMap/Secret/PVC 分離

---

## 11. 設定モデル仕様（テンプレート）

| key | type | range | default | on_error | audit_log |
|---|---|---|---|---|---|
| `runtime.mode` | enum | backtest/paper/live | live | fail_fast | yes |
| `runtime.interval_seconds` | int | 5..3600 | 300 | clamp | yes |
| `exchange.name` | enum | gmo | gmo | fail_fast | yes |
| `exchange.product_type` | enum | spot/leverage | spot | fail_fast | yes |
| `risk.max_drawdown` | float | 0..1 | 0.2 | abort | yes |
| `risk.daily_loss_limit` | float | >0 | profile依存 | abort | yes |
| `strategy.min_confidence` | float | 0..1 | 0.55 | hold | no |
| `optimizer.opt_trials` | int | 1..500 | 50 | clamp | yes |
| `notify.discord.enabled` | bool | - | true | continue | yes |

---

## 12. テスト戦略（本番合格基準）

## 12.1 必須品質ゲート

- lint
- type check
- unit test
- integration test
- replay test（決定論）

## 12.2 契約テスト

- run_complete マーカー出力テスト
- Discord失敗時の非致命テスト
- monitor status 遷移テスト
- opt_trials クランプテスト

## 12.3 取引所アダプタテスト

- 現物/レバ切替
- 注文失敗時のエラー正規化
- 再試行・レート制限

---

## 13. セキュリティ・監査仕様

- APIキーの保存先を限定
- 秘密情報をログに出さない
- 監査イベント（注文/取消/停止/設定変更）保存
- NTP 時刻同期必須
- ログ保管期間とアクセス権限の定義

---

## 14. Docker Compose 仕様（最小）

- bot コンテナ
- （任意）prometheus コンテナ
- （任意）grafana コンテナ

必須:
- `healthcheck`
- `restart`
- `volumes`
- `env/secrets`
- `logging`（max-size/max-file）

---

## 15. Definition of Done（本番仕様完成条件）

### 高優先
- GMO現物/レバ差分表が承認済み
- run_complete JSON スキーマ凍結
- 自動停止条件と縮退条件が承認済み
- Discord失敗時非致命がテストで担保済み
- Docker常駐で24h連続稼働検証済み

### 中優先
- replayテストとフェイルオーバー試験完了
- 監視ダッシュボード最小セット運用開始
- 鍵ローテーション演習完了

### 低優先
- K8s 運用手順書（ローリング更新/ロールバック）完成
- 月次レポート自動化

---

## 16. Copilot Chat 実装ガイド（別ワークスペース向け）

実装は以下順序を推奨:

1. 設定モデル + validator
2. run_complete 契約
3. exchange adapter 抽象 + GMO spot
4. GMO leverage 追加
5. 指標/戦略/リスク
6. backtest + optimizer
7. live daemon + Discord
8. Docker/K8s 運用 + 監視

Copilot への指示は常に以下を含める:
- 入力/出力スキーマ
- 失敗時挙動
- テスト観点
- 後方互換（JSON契約）

---

## 17. 既存知見からの移植ルール（重要）

- コードはコピーしない
- 仕様・契約・テスト観点のみ移植
- 契約破壊（run_complete形式、監視ラベル）は禁止
- 変更時は必ずスキーマバージョンを更新

---

## 18. 付録: 主要 reason code 候補

- `missing_credentials`
- `execute_orders_disabled`
- `monitor_disabled`
- `risk_limit_exceeded`
- `wallet_drift_exceeded`
- `rate_limit`
- `exchange_validation_error`
- `network_timeout`
- `graceful_shutdown_requested`

この一覧は固定値辞書として管理し、通知・監査・分析で共通利用する。

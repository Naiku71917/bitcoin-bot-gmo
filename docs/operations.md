# Operations

- Docker Compose で常駐実行
- 生成物は `var/artifacts`, ログは `var/logs`

## 日常運用コマンド

```bash
# 起動（build込み）
docker-compose up -d --build

# 停止
docker-compose down

# 稼働/ヘルス確認
docker-compose ps
curl -fsS http://127.0.0.1:9754/healthz
```

## Secretsファイル運用（推奨）

```bash
mkdir -p secrets
printf '%s' '<GMO_API_KEY>' > secrets/gmo_api_key
printf '%s' '<GMO_API_SECRET>' > secrets/gmo_api_secret
printf '%s' '<DISCORD_WEBHOOK_URL>' > secrets/discord_webhook_url

# 起動
docker-compose up -d --build
```

- `docker-compose.yml` は `/run/secrets/*` を優先読込します。
- 既存の環境変数指定（`GMO_API_KEY` など）も引き続き利用可能です（後方互換）。

## 実運用前スモーク検証

```bash
# 正常系（終了コード0）
bash scripts/smoke_live_daemon.sh

# 異常系シミュレーション（終了コード非0 + 診断出力）
bash scripts/smoke_live_daemon.sh --simulate-failure

# 反復実行（24h相当の事前確認向け）
SMOKE_REPEAT_COUNT=3 bash scripts/smoke_live_daemon.sh
```

- `SMOKE_REPEAT_COUNT` を指定すると、health/artifacts 検証を指定回数反復します。
- 失敗時は即終了し、`failed_iteration=<失敗回>/<総回数>` を出力します。

## リリース前フルチェック

```bash
bash scripts/release_check.sh
```

- `release_check.sh` は以下を順に実行し、失敗した段階名を出力して非0終了します。
	- pre-commit
	- pytest（quick）
	- pytest（coverage）
	- smoke_live_daemon

## 本番移行 Go/No-Go 判定

当日判定は以下を上から順に確認し、1つでも未達なら No-Go。

- release_check 成功
	- `bash scripts/release_check.sh`
- smoke 反復成功
	- `SMOKE_REPEAT_COUNT=3 bash scripts/smoke_live_daemon.sh`
- secrets 設定確認
	- `secrets/gmo_api_key`
	- `secrets/gmo_api_secret`
	- （利用時）`secrets/discord_webhook_url`
- health/metrics 確認
	- `curl -fsS http://127.0.0.1:9754/healthz`
	- `curl -fsS http://127.0.0.1:9754/metrics`

Go 条件:
- 全チェック成功
- `run_progress.json` の `monitor_status` が `active` または `reconnecting` の想定範囲
- `run_complete.json` が最新実行で生成済み

No-Go 条件:
- コマンド失敗
- smoke 反復途中失敗
- health/metrics 応答不可

## 最小ロールバック手順

```bash
# 1) 即時停止
docker-compose down

# 2) 直前安定設定へ復帰（例: config/secrets を戻す）
#    必要に応じて git で安定コミットへ戻す
#    git checkout <stable_commit> -- configs docker-compose.yml scripts

# 3) 再起動
docker-compose up -d --build

# 4) ヘルス確認
curl -fsS http://127.0.0.1:9754/healthz
```

## 連絡/エスカレーション（プレースホルダ）

- 1次連絡先: `<ONCALL_PRIMARY>`
- 2次連絡先: `<ONCALL_SECONDARY>`
- エスカレーションチャネル: `<INCIDENT_CHANNEL>`
- 連絡時に添付する情報:
	- `docker-compose ps`
	- `docker-compose logs --tail=200 bot`
	- `var/artifacts/run_progress.json`
	- `var/artifacts/run_complete.json`

## 監査ログローテーション

- 監査ログは `var/logs/audit_events.jsonl` に出力され、サイズ上限超過時にローテーションされます。
- 保持世代数は環境変数で制御できます。

```bash
# 例: 1MB上限 / 7世代保持
export AUDIT_LOG_MAX_BYTES=1048576
export AUDIT_LOG_RETENTION=7
python scripts/run_live.py
```

## 鍵ローテーション演習（最小）

```bash
bash scripts/rotate_secrets_check.sh
```

- 旧secrets -> 新secrets の切替を自動検証します。
- 各フェーズで以下を確認します。
	- `healthz`
	- `metrics`
	- `smoke_live_daemon.sh`
- 秘密値そのものは出力しません（プレースホルダ値で演習）。

## 監視運用（最小）

- 指標定義とダッシュボード項目は `docs/monitoring.md` を参照。
- 監視UIが必要な場合のみ、以下で monitoring profile を起動。

```bash
docker-compose --profile monitoring up -d
```

### アラート閾値（例）

- `run_loop_failures_total` が 5分で `+3` 以上
- `monitor_status{status="degraded"}` が 2分以上継続
- `monitor_status{status="reconnecting"}` が 5分以上継続

## 一次切り分け（短縮版）

- Logs:
	- `docker-compose logs --tail=200 bot`
- Artifacts:
	- `var/artifacts/run_progress.json`（直近ステータス/監視状態）
	- `var/artifacts/run_complete.json`（終了サマリ/停止理由）
- Health:
	- `docker-compose ps` が `healthy` か
	- `/healthz` が `200` を返すか

補足:
- `scripts/smoke_live_daemon.sh` は異常時に `docker-compose ps` / `docker-compose logs --tail=200 bot` / artifacts を自動出力する。

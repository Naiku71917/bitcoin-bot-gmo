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

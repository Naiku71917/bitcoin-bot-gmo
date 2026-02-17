# bitcoin-bot-gmo

GMOコイン対応のビットコイン売買システム向け、Python 3.12ベースの初期スケルトンです。

## セットアップ

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pre-commit install
```

## 実行

```bash
python -m bitcoin_bot.main --config configs/runtime.example.yaml --mode backtest
python -m bitcoin_bot.main --config configs/runtime.live.spot.yaml --mode live

# 常駐実行
docker-compose up -d --build
```

## テスト

```bash
pytest -q
```

## pre-commit

```bash
pre-commit run --all-files
```

## 品質ゲート

```bash
pre-commit run --all-files
pytest -q --cov=src/bitcoin_bot --cov-report=term-missing --cov-report=xml --cov-report=html
```

## 生成物

- `var/artifacts/run_progress.json`
	- `status`, `updated_at`, `mode`, `last_error`, `monitor_status`, `reconnect_count`
- `var/artifacts/run_complete.json`
	- 実行完了サマリ（`pipeline_summary`, `optimization`, `notifications` など）

## 運用コマンド

```bash
# 停止
docker-compose down

# 稼働/ヘルス確認
docker-compose ps
curl -fsS http://127.0.0.1:9754/healthz
```

## 起動前環境変数チェック（live）

- `runtime.execute_orders=true` の場合は以下が必須です。
	- `GMO_API_KEY`
	- `GMO_API_SECRET`
- 不足時は `scripts/run_live.py` が起動失敗し、`run_progress.json` に検証結果を残します。
- Discord通知が有効で webhook 環境変数未設定の場合は非致命で継続し、検証結果に `status=failed` が記録されます。

## 障害時の一次確認

```bash
docker-compose logs --tail=200 bot
cat var/artifacts/run_progress.json
cat var/artifacts/run_complete.json
```

# Architecture

`main.run` が mode ごとに pipeline runner を切り替え、終了時に `run_complete` 契約を出力する。

## Runtime Contracts

- `run_complete`:
	- 出力先: `var/artifacts/run_complete.json`（atomic write）
	- STDOUT マーカー: `BEGIN_RUN_COMPLETE_JSON` / `END_RUN_COMPLETE_JSON`
	- `pipeline_summary` に `opt_trials_executed` と live時の `monitor_summary` を保持
- `run_progress`:
	- 出力先: `var/artifacts/run_progress.json`（atomic write）
	- 主キー: `status`, `updated_at`, `mode`, `last_error`, `monitor_status`, `reconnect_count`

## Live Daemon

- 実行エントリ: `scripts/run_live.py`
- 監視エンドポイント: `GET /healthz`（既定ポート `9754`）
- graceful shutdown: `SIGTERM`/`SIGINT` 受信で停止処理へ移行

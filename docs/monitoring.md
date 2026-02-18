# Monitoring

## 最小ダッシュボード定義

対象メトリクス（既存 `/metrics`）:
- `run_loop_total`
- `run_loop_failures_total`
- `monitor_status`

推奨パネル（最小）:
1. **Run Loop Total**
   - Query: `run_loop_total`
   - 型: Counter
2. **Run Loop Failures Total**
   - Query: `run_loop_failures_total`
   - 型: Counter
3. **Monitor Status**
   - Query: `monitor_status`
   - 値: `degraded=0`, `active=1`, `reconnecting=2`

## 監視手順（当日参照）

### 1) Botのメトリクス確認

```bash
curl -fsS http://127.0.0.1:9754/metrics
```

### 2) 任意: Prometheus / Grafana を起動

```bash
docker-compose --profile monitoring up -d
```

- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`（`admin/admin`）

### 3) Grafanaで最小パネルを作成

- Data Source: Prometheus (`http://prometheus:9090`)
- Panels:
  - `run_loop_total`
  - `run_loop_failures_total`
  - `monitor_status`

## アラート閾値（例）

- `increase(run_loop_failures_total[5m]) >= 3`
- `monitor_status{status="degraded"} == 0` が2分継続
- `monitor_status{status="reconnecting"} == 2` が5分継続

## 障害時の即応メモ

- `monitor_status=0`（degraded）なら Runbook の No-Go 判定を優先
- `run_loop_failures_total` が連続増加する場合は再接続上限と secrets を確認
- 切り分け時は以下を採取:
  - `docker-compose logs --tail=200 bot`
  - `var/artifacts/run_progress.json`
  - `var/artifacts/run_complete.json`

## 実接続ドリル結果の見方

```bash
bash scripts/live_connectivity_drill.sh
```

- 成果物: `var/artifacts/live_connectivity_drill.json`
- 失敗カテゴリ:
   - `auth`: APIキー/シークレット不備
   - `network`: 通信断/タイムアウト
   - `rate_limit`: API制限
   - `exchange`: 取引所応答異常/想定外形式

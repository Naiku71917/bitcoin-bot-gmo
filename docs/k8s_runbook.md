# Kubernetes Runbook (Minimal)

この文書は将来のK8s移行に向けた最小運用手順です。現行本番運用の正規手順は Docker Compose を維持します。

## 0. 前提

- 現行の Go/No-Go 判定は Docker Compose ベースで実施。
- K8s は移行準備用の先行手順として扱う。
- 変更時も run_complete / run_progress 契約は維持する。

## 1. Secret / ConfigMap / PVC 分離方針

- Secret
  - GMO API key/secret
  - Discord webhook URL
  - 例: `gmo-bot-secrets`
- ConfigMap
  - 実行モード、interval、監視設定
  - 例: `gmo-bot-config`
- PVC
  - `var/artifacts`, `var/logs`, `var/cache`
  - 例: `gmo-bot-var-pvc`

運用ルール:
- 機密値は Secret のみ。
- 設定値は ConfigMap に分離。
- 監査・成果物は PVC に永続化。

## 2. Probe 設定例

```yaml
readinessProbe:
  httpGet:
    path: /healthz
    port: 9754
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3

livenessProbe:
  httpGet:
    path: /healthz
    port: 9754
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3

startupProbe:
  httpGet:
    path: /healthz
    port: 9754
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 24
```

## 3. Rolling Update（最小）

1. 新イメージを適用
2. rollout 状態を監視
3. 新Podで以下を確認
   - `/healthz`
   - `/metrics`
   - 最新 `run_progress.json` 更新

```bash
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/bitcoin-bot-gmo -n bot
kubectl get pods -n bot
kubectl logs deploy/bitcoin-bot-gmo -n bot --tail=200
```

判定:
- rollout 完了 + health 良好なら継続。
- degraded/failed 傾向なら即 rollback。

## 4. Rollback（最小）

```bash
kubectl rollout undo deployment/bitcoin-bot-gmo -n bot
kubectl rollout status deployment/bitcoin-bot-gmo -n bot
kubectl get pods -n bot
kubectl logs deploy/bitcoin-bot-gmo -n bot --tail=200
```

復旧確認:
- `/healthz` が 200
- `monitor_status` が `active` or `reconnecting`
- `run_complete.json` の最新生成

## 5. 既存運用との整合チェック

- Docker Compose 手順と K8s 手順の二重管理はしない。
- 判定基準（Go/No-Go、reason code、risk matrix）は共通化する。
- K8s本番適用前は必ず Docker 側の `bash scripts/go_nogo_gate.sh` を通す。

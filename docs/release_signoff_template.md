# Release Signoff Template

このテンプレートは本番投入日のサインオフ記録に使用します。
`bash scripts/go_live_prep.sh` 実行時に、同形式の記録が自動生成されます。

- 記録先: `var/artifacts/release_signoff_YYYYMMDD.md`

## 判定サマリ

- decision: `<GO|NO-GO>`
- generated_at: `<ISO8601>`
- failed_stage: `<stage or empty>`
- require_auth: `<0|1>`
- auth_ready: `<0|1>`

## 実接続ドリル

- mode: `<real_connect|non_destructive|not_run>`
- passed: `<true|false|unknown>`
- failed_categories: `<auth:1,network:2 形式 or none>`

## 実行情報

- preflight_log: `<var/artifacts/go_live_prep.log>`
- preflight_summary: `<var/artifacts/go_live_prep_summary.json>`
- live_drill_artifact: `<var/artifacts/live_connectivity_drill.json>`

## サインオフ

- 担当: `<name>`
- レビュー: `<name>`
- 承認: `<name>`
- 備考: `<memo>`

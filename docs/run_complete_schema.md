# run_complete Schema

必須トップレベル: `schema_version`, `run_id`, `started_at`, `completed_at`, `pipeline`, `pipeline_summary`, `optimization`, `notifications`。

- 現行固定値: `schema_version = "1.0.0"`

## version変更手順

1. `src/bitcoin_bot/telemetry/reporters.py` の `RUN_COMPLETE_SCHEMA_VERSION` を更新
2. `docs/run_complete_schema.md` の現行固定値を更新
3. 互換性影響がある場合は `tests/test_main_contract.py` と `tests/test_run_complete_schema_version.py` を更新
4. 以下を実行して契約非破壊を確認
	- `pytest -q tests/test_main_contract.py`
	- `pytest -q tests/test_run_complete_schema_version.py`

# Skill: config-validation

## 目的
設定モデル・ローダー・バリデーターを一貫して更新し、fail-fast と正規化契約を維持する。

## 前提（必須）
- このSkill適用時は Serena MCP で `models/loader/validator` と関連テストを先に確認する。

## 使うタイミング
- `configs/*.yaml` の項目を追加/変更する時
- `RuntimeConfig` や各Settings dataclassを変更する時
- バリデーション条件（許容値・クランプ）を変更する時
- `validate_runtime_environment()` の必須環境変数ルールを変更する時

## 主な編集対象
- `src/bitcoin_bot/config/models.py`
- `src/bitcoin_bot/config/loader.py`
- `src/bitcoin_bot/config/validator.py`
- `configs/runtime.example.yaml`
- `tests/test_config_validation.py`
- `tests/test_execute_orders_flag.py`
- `tests/test_runtime_env_validation.py`

## 実行手順
1. `models.py` の `dataclass(slots=True)` に項目を追加。
2. `loader.py` で YAML section から新項目が読み込まれることを確認。
3. `validator.py` に fail-fast 条件と必要な正規化（例: clamp）を追加。
4. live + `execute_orders=true` 時の `GMO_API_KEY`/`GMO_API_SECRET` 必須チェックを維持。
5. `paths.*` 系を追加した場合は `mkdir(parents=True, exist_ok=True)` 経路を維持。
6. `tests/test_config_validation.py` と周辺テストに成功/失敗ケースを追加。

## 非交渉契約
- `runtime.mode` / `exchange.product_type` の fail-fast を維持する。
- `optimizer.opt_trials` の `1..500` クランプを維持する。

## 完了条件
- `runtime.mode` と `exchange.product_type` の許容値制約を壊していない。
- `runtime.execute_orders` が bool として検証される。
- `optimizer.opt_trials` の `1..500` クランプが維持される。
- `pytest -q tests/test_config_validation.py tests/test_execute_orders_flag.py tests/test_runtime_env_validation.py` が通る。

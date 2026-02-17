# Skill: config-validation

## 目的
設定モデル・ローダー・バリデーターを一貫して更新し、fail-fast と正規化契約を維持する。

## 使うタイミング
- `configs/*.yaml` の項目を追加/変更する時
- `RuntimeConfig` や各Settings dataclassを変更する時
- バリデーション条件（許容値・クランプ）を変更する時

## 主な編集対象
- `src/bitcoin_bot/config/models.py`
- `src/bitcoin_bot/config/loader.py`
- `src/bitcoin_bot/config/validator.py`
- `configs/runtime.example.yaml`
- `tests/test_config_validation.py`

## 実行手順
1. `models.py` の `dataclass(slots=True)` に項目を追加。
2. `loader.py` で YAML section から新項目が読み込まれることを確認。
3. `validator.py` に fail-fast 条件と必要な正規化（例: clamp）を追加。
4. `paths.*` 系を追加した場合は `mkdir(parents=True, exist_ok=True)` 経路を維持。
5. `tests/test_config_validation.py` に成功/失敗ケースを追加。

## 完了条件
- `runtime.mode` と `exchange.product_type` の許容値制約を壊していない。
- `optimizer.opt_trials` の `1..500` クランプが維持される。
- `pytest -q tests/test_config_validation.py` が通る。

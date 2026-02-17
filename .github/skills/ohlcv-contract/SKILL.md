# Skill: ohlcv-contract

## 目的
OHLCV入力データの最小契約（列/時刻型）を壊さずに、データ処理を拡張する。

## 使うタイミング
- `data/ohlcv.py` の検証ロジックを変更する時
- 必須列や時刻の扱いを拡張する時
- データ前処理の受け入れ条件を追加する時

## 主な編集対象
- `src/bitcoin_bot/data/ohlcv.py`
- `tests/test_ohlcv_contract.py`

## 実行手順
1. 必須列 `timestamp, open, high, low, close, volume` の契約を維持。
2. `timestamp` は `datetime` 型で判定する現行契約を基準に変更可否を判断。
3. 追加検証を入れる場合は、既存の True ケースと失敗ケースを両方テスト化。
4. 仕様変更時は `docs/api_contracts.md` または `docs/spec.md` の整合も確認。

## 完了条件
- 既存のOHLCV契約テストが通る。
- `pytest -q tests/test_ohlcv_contract.py` が通る。

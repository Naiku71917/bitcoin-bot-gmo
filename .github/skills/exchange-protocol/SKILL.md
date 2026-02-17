# Skill: exchange-protocol

## 目的
`ExchangeProtocol` 境界を維持しつつ、GMO adapter（現物/レバ）を安全に変更する。

## 前提（必須）
- このSkill適用時は Serena MCP で `protocol.py` の型契約と `gmo_adapter.py` の参照関係を先に確認する。

## 使うタイミング
- `exchange/protocol.py` の抽象メソッドや正規化モデルを変更する時
- `exchange/gmo_adapter.py` の返却形式や product_type 挙動を変更する時
- spot/leverage 差分吸収ロジックを追加する時

## 主な編集対象
- `src/bitcoin_bot/exchange/protocol.py`
- `src/bitcoin_bot/exchange/gmo_adapter.py`
- `tests/test_exchange_protocol.py`
- `tests/test_exchange_error_normalization.py`
- `tests/test_exchange_runtime_integration.py`

## 実行手順
1. 先に `protocol.py` の契約を確定し、上位層へGMO固有仕様を漏らさない。
2. `gmo_adapter.py` で protocol の各メソッドを実装し、返却型（`Normalized*`）を崩さない。
3. `NormalizedOrder` / `NormalizedFill` / `NormalizedError` を変更した場合は利用箇所を同時更新。
4. `normalize_error()` の category/retryable 規則（auth/rate_limit/validation/network/exchange）を維持。
5. HTTP連携 (`use_http=True`) 変更時は認証ヘッダー生成と失敗時 `NormalizedError` 返却を維持。
6. `product_type` の分岐追加時は、spot/leverageの両ケースをテストに含める。

## 完了条件
- `isinstance(adapter, ExchangeProtocol)` を満たす。
- `pytest -q tests/test_exchange_protocol.py tests/test_exchange_error_normalization.py tests/test_exchange_runtime_integration.py` が通る。

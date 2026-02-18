# GMO Spot/Leverage 差分マトリクス

この文書は `src/bitcoin_bot/exchange/gmo_adapter.py` の現行実装と、対応テストの対応関係を固定するための差分表です。

## 差分表（実装整合済み）

| 項目 | spot | leverage | 実装（現行） | 対応テスト |
|---|---|---|---|---|
| `reduce_only` | 常に `None`（無効） | `order_request.reduce_only` を保持 | `GMOAdapter.place_order` で `self._is_leverage` 判定 | `test_gmo_adapter_spot_leverage_switching`, `test_order_reduce_only_constraint_by_product_type` |
| balances 取得経路 | `/private/v1/account/assets` | `/private/v1/account/assets` | `fetch_balances(..., auth=True)` で同一経路 | `test_fetch_balances_uses_assets_endpoint` |
| positions 取得経路 | `/private/v1/openPositions`（空でも許容） | `/private/v1/openPositions`（建玉あり想定） | `fetch_positions(..., auth=True)` で同一経路 | `test_fetch_positions_uses_open_positions_endpoint`, `test_fetch_positions_failure_returns_error_aware_empty_list` |
| 注文属性（side/order_type/qty/price） | 正規化値をそのまま採用 | 正規化値をそのまま採用 | `place_order` の `NormalizedOrderState` に写像 | `test_gmo_adapter_spot_leverage_switching`, `test_order_reduce_only_constraint_by_product_type` |
| read失敗時フォールバック | `ErrorAwareList([])` / `fetch_order: status=error` | `ErrorAwareList([])` / `fetch_order: status=error` | `fetch_klines`, `fetch_positions`, `fetch_order` で統一 | `test_fetch_klines_failure_returns_error_aware_empty_list`, `test_fetch_positions_failure_returns_error_aware_empty_list`, `test_fetch_order_failure_keeps_error_status_and_product_type` |

## 注文属性と制約（運用向け要点）

- `reduce_only` は leverage のみ有効。spot では常に `None`。
- `side/order_type/qty/price` は `NormalizedOrder` から `NormalizedOrderState` に引き継ぐ。
- `fetch_order` の `reduce_only` は leverage 時のみ `settleType` 由来で評価し、spot では `None`。

## レビュー観点

- この表の各行は上記テスト名で追跡可能であること。
- `gmo_adapter.py` の変更時は、差分表とテスト名を同時更新すること。

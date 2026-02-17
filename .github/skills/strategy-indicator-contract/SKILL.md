# Skill: strategy-indicator-contract

## 目的
`strategy` 出力契約と `indicators` 列契約を維持しながら、意思決定ロジックを安全に変更する。

## 前提（必須）
- このSkill適用時は Serena MCP で `strategy/core.py` と `indicators/generator.py`、関連テストを先に確認する。

## 使うタイミング
- `StrategyDecision` の schema（`action/confidence/reason_codes/risk`）を変更する時
- `decide_action()` の判定条件や hooks（`min_confidence`, `cooldown`）を変更する時
- `generate_indicators()` の列名・window・feature_flags を変更する時

## 主な編集対象
- `src/bitcoin_bot/strategy/core.py`
- `src/bitcoin_bot/indicators/generator.py`
- `src/bitcoin_bot/pipeline/paper_runner.py`
- `tests/test_strategy_contract.py`
- `tests/test_indicator_contract.py`
- `tests/test_paper_runner_contract.py`

## 実行手順
1. `StrategyDecision` の `action in {buy,sell,hold}` と `confidence in [0,1]` 制約を維持。
2. `risk` の必須キー（`sl`, `tp`, `max_holding_bars`）を維持。
3. 指標列の命名規約（`ema_*`, `rsi_*`, `atr_*`, `slope_norm`, `gap_norm`）を維持。
4. 既存列上書き禁止（衝突時 ValueError）を維持。
5. paper runner の `summary.order_count` と `paper_order_events` の整合を維持。

## 非交渉契約
- `StrategyDecision` の出力キー（action/confidence/reason_codes/risk）を維持する。
- 指標列の既存命名規約と衝突時エラー挙動を維持する。

## 完了条件
- `pytest -q tests/test_strategy_contract.py tests/test_indicator_contract.py tests/test_paper_runner_contract.py` が通る。

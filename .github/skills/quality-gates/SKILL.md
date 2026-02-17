# Skill: quality-gates

## 目的
ローカル検証をCIと一致させ、品質ゲート（lint/format/type/test）を崩さずに変更を出す。

## 前提（必須）
- このSkill適用時は Serena MCP で変更シンボルの参照先を確認し、最小の対象テスト集合を先に決める。

## 使うタイミング
- 変更後の最終確認をする時
- CI落ちをローカルで再現したい時
- pre-commit や依存更新を調整する時

## 主な確認対象
- `.pre-commit-config.yaml`
- `pyproject.toml`
- `.github/workflows/ci.yml`

## 実行手順
1. 環境セットアップ: `python3.12 -m venv .venv && source .venv/bin/activate && pip install -e .[dev]`
2. 品質ゲート: `pre-commit run --all-files`
3. テスト: `pytest -q`
4. 契約変更時は対象別に絞って先行実行（例: main/live/exchange/strategy）。
5. 失敗時は、失敗した対象ファイル周辺のみ最小修正して再実行。

## 完了条件
- `pre-commit run --all-files` が通る。
- `pytest -q` が通る。
- CI（`.github/workflows/ci.yml`）と同一コマンド体系で確認できている。

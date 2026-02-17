# bitcoin-bot-gmo

GMOコイン対応のビットコイン売買システム向け、Python 3.12ベースの初期スケルトンです。

## セットアップ

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 実行

```bash
python -m bitcoin_bot.main --config configs/runtime.example.yaml --mode backtest
python -m bitcoin_bot.main --config configs/runtime.live.spot.yaml --mode live
```

## テスト

```bash
pytest -q
```

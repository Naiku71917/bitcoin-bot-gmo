from __future__ import annotations

import json

from bitcoin_bot.main import run


def test_main_run_emits_run_complete(tmp_path, capsys):
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        """
runtime:
  mode: backtest
exchange:
  product_type: spot
optimizer:
  enabled: true
  opt_trials: 2
notify:
  discord:
    enabled: false
paths:
  artifacts_dir: "./var/artifacts"
  logs_dir: "./var/logs"
  cache_dir: "./var/cache"
""",
        encoding="utf-8",
    )

    result = run(mode="backtest", config_path=str(config_path))

    out = capsys.readouterr().out
    assert "BEGIN_RUN_COMPLETE_JSON" in out
    assert "END_RUN_COMPLETE_JSON" in out
    assert result["pipeline"]["mode"] == "backtest"

    artifact = json.loads(open("var/artifacts/run_complete.json", encoding="utf-8").read())
    assert "run_id" in artifact
    assert "pipeline" in artifact

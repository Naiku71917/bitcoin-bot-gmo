# Architecture

`main.run` が mode ごとに pipeline runner を切り替え、終了時に `run_complete` 契約を出力する。

#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
exec .venv-build/bin/python3 open_strategy_study.py

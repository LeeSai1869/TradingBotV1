#!/bin/zsh
cd -- "$(dirname -- "$0")/../.." || exit 1
exec .venv-build/bin/python3 -m Section_12_Research.cli.open_strategy_study

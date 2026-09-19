import sys
from app.cli.main import run_cli

sys.argv = ["ntrade", "research", "--name", "LineageTest", "--strategy", "breakout"]
run_cli()

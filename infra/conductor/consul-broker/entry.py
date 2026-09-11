"""Immutable import roots; the broker owns bounded stdin and protected config."""

from pathlib import Path
import runpy
import sys

release = Path(__file__).resolve().parent
sys.path[:0] = [
    str(release / "site-packages"),
    str(release / "src"),
    str(release / "src/apps/backend-rag"),
    str(release / "src/packages/research-os-core"),
]
runpy.run_module("scripts.consul_broker", run_name="__main__")

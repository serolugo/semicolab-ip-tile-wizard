"""
tests/runner.py — entry point for the TileWizard integration test suite.
"""
import os
import sys

# Make sure the repo root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_tilewizard import run_all

run_all()

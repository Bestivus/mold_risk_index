"""Installs lightweight Home Assistant stubs (see ha_stubs.py) before any
test module imports custom_components.mold_risk_index.sensor. Runs once,
before test collection.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ha_stubs  # noqa: E402

ha_stubs.install()

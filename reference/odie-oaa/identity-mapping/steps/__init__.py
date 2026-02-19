"""
Identity mapping steps package.

Steps:
  1. fetch_ad_config    — Fetch AD provider integrations and mapping state
  2. fetch_custom_apps  — Discover OAA custom application providers
  3. build_mapping      — Build the identity mapping report
  4. apply_mapping      — Apply mappings to the AD provider
"""

import os
from datetime import datetime

from steps.fetch_ad_config import fetch_ad_config
from steps.fetch_custom_apps import fetch_custom_apps
from steps.build_mapping import build_mapping
from steps.apply_mapping import apply_mappings

__all__ = [
    "fetch_ad_config",
    "fetch_custom_apps",
    "build_mapping",
    "apply_mappings",
    "get_day_dir",
]


def get_day_dir() -> str:
    """Return the daily output directory path (output/YYYY-MM-DD/) and ensure it exists."""
    day = datetime.now().strftime("%Y-%m-%d")
    day_dir = os.path.join("output", day)
    os.makedirs(day_dir, exist_ok=True)
    return day_dir

"""
Provider Registry - Provider ID persistence.
Tracks which providers were created by a connector for auto-override on subsequent runs.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional


class ProviderRegistry:
    """Manages provider ID persistence and tracking."""

    REGISTRY_FILENAME = "oaa_provider_ids.json"

    def __init__(self, output_dir: str, debug: bool = False):
        self.output_dir = output_dir
        self.debug = debug
        self._registry_path = os.path.join(output_dir, self.REGISTRY_FILENAME)

    def load(self) -> Dict[str, str]:
        """Load previous provider IDs. Returns dict of provider_name -> provider_id."""
        previous_ids = {}

        if not os.path.exists(self._registry_path):
            if self.debug:
                print(f"  No registry file found at {self._registry_path}")
            return previous_ids

        try:
            with open(self._registry_path, 'r') as f:
                data = json.load(f)

            for provider in data.get("providers", []):
                name = provider.get("name")
                pid = provider.get("id")
                if name and pid:
                    previous_ids[name] = pid

            if self.debug:
                print(f"  Loaded {len(previous_ids)} provider IDs from registry")

        except (json.JSONDecodeError, IOError) as e:
            if self.debug:
                print(f"  Could not load registry: {e}")

        return previous_ids

    def save(self, providers: List[Dict], veza_url: str, provider_prefix: str = "") -> str:
        """Save provider IDs to registry file."""
        os.makedirs(self.output_dir, exist_ok=True)

        registry_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "veza_url": veza_url,
            "provider_prefix": provider_prefix,
            "providers": providers,
        }

        with open(self._registry_path, 'w') as f:
            json.dump(registry_data, f, indent=2)

        if self.debug:
            print(f"  Saved {len(providers)} provider IDs to registry")

        return self._registry_path

    def load_full(self) -> Dict[str, Dict]:
        """Load full provider records including data source IDs."""
        records = {}

        if not os.path.exists(self._registry_path):
            return records

        try:
            with open(self._registry_path, 'r') as f:
                data = json.load(f)

            for provider in data.get("providers", []):
                name = provider.get("name")
                if name:
                    records[name] = {
                        "id": provider.get("id"),
                        "app_id": provider.get("app_id"),
                        "app_name": provider.get("app_name"),
                        "data_sources": provider.get("data_sources", []),
                    }

        except (json.JSONDecodeError, IOError) as e:
            if self.debug:
                print(f"  Could not load registry: {e}")

        return records

    def is_our_provider(self, provider_name: str, provider_id: str) -> bool:
        """Check if a provider matches our previous run."""
        previous_ids = self.load()
        previous_id = previous_ids.get(provider_name)
        return previous_id is not None and previous_id == provider_id

    def get_registry_path(self) -> str:
        return self._registry_path

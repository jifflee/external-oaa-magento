"""
Preflight Checker - Validates environment before running.
"""

from typing import Optional
from dataclasses import dataclass, field


@dataclass
class PreflightResult:
    proceed: bool = True
    conflicts: list = field(default_factory=list)
    has_conflicts: bool = False
    override_provider: bool = False
    existing_provider_id: Optional[str] = None
    existing_data_source_id: Optional[str] = None


class PreflightChecker:
    def __init__(self, veza_client, registry, provider_prefix: str = "", debug: bool = False):
        self.veza_client = veza_client
        self.registry = registry
        self.provider_prefix = provider_prefix
        self.debug = debug

    def check(self, provider_name: str, dry_run: bool = False) -> PreflightResult:
        result = PreflightResult()
        if dry_run:
            return result
        if not self.veza_client.veza_url or not self.veza_client.veza_api_key:
            return result
        full_name = self.veza_client.generate_provider_name(provider_name, self.provider_prefix)
        try:
            existing = self.veza_client.get_provider(full_name)
            if existing:
                existing_id = existing.get("id")
                if self.registry.is_our_provider(full_name, existing_id):
                    result.override_provider = True
                    result.existing_provider_id = existing_id
                    try:
                        ds_list = self.veza_client.get_data_sources(existing_id)
                        if ds_list:
                            result.existing_data_source_id = ds_list[0].get("id")
                    except Exception:
                        pass
                else:
                    result.has_conflicts = True
                    result.conflicts.append({
                        "provider_name": full_name,
                        "existing_id": existing_id,
                        "reason": "Provider exists but was not created by this connector",
                    })
                    print(f"  WARNING: Provider '{full_name}' already exists (external)")
        except Exception as e:
            if self.debug:
                print(f"  Preflight: Error checking provider: {e}")
        return result

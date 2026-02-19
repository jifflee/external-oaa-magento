"""
Push Helper - Shared Veza push sequence used by all connector orchestrators.

Extracts the preflight-check -> push -> save_provider_ids sequence that was
duplicated across all orchestrators.
"""

import json
from typing import Dict, Any, Optional


def execute_veza_push(
    veza_client,
    preflight_checker,
    registry,
    app,
    provider_name: str,
    provider_prefix: str,
    company: Dict,
    veza_url: str,
    debug: bool = False,
) -> Dict[str, Any]:
    """Execute the full Veza push sequence.

    Steps:
    1. Preflight check for conflicts
    2. Generate provider name
    3. Push application (by IDs if overriding, or fresh)
    4. Save provider IDs to registry

    Returns:
        Dict with provider_name, veza_response, and any warnings
    """
    result = {}

    # Preflight check
    preflight = preflight_checker.check(provider_name, dry_run=False)

    if preflight.has_conflicts:
        print("  WARNING: Provider conflicts detected")
        for conflict in preflight.conflicts:
            print(f"    - {conflict['provider_name']}: {conflict['reason']}")

    full_provider_name = veza_client.generate_provider_name(provider_name, provider_prefix)

    # Push
    if preflight.override_provider and preflight.existing_provider_id:
        if preflight.existing_data_source_id:
            response = veza_client.push_application_by_ids(
                app,
                preflight.existing_provider_id,
                preflight.existing_data_source_id,
            )
        else:
            veza_client.ensure_provider(full_provider_name)
            response = veza_client.push_application(
                app, full_provider_name, company.get("name", ""),
            )
    else:
        veza_client.ensure_provider(full_provider_name)
        response = veza_client.push_application(
            app, full_provider_name, company.get("name", ""),
        )

    result["veza_response"] = response
    result["provider_name"] = full_provider_name
    print(f"  Pushed to Veza as: {full_provider_name}")

    # Save provider IDs
    _save_provider_ids(veza_client, registry, full_provider_name, company, veza_url, debug)

    return result


def _save_provider_ids(veza_client, registry, provider_name, company, veza_url, debug):
    """Save provider IDs after successful push."""
    try:
        provider = veza_client.get_provider(provider_name)
        if provider:
            provider_id = provider.get("id")
            data_sources = []
            try:
                ds_list = veza_client.get_data_sources(provider_id)
                for ds in ds_list:
                    data_sources.append({"name": ds.get("name"), "id": ds.get("id")})
            except Exception:
                pass

            providers = [{
                "name": provider_name,
                "id": provider_id,
                "app_name": company.get("name", ""),
                "data_sources": data_sources,
            }]
            registry.save(providers, veza_url)
    except Exception as e:
        if debug:
            print(f"  Warning: Could not save provider IDs: {e}")

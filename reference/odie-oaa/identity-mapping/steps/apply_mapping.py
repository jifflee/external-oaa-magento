"""
Step 4: Apply identity mappings to the AD provider, one app at a time.

Safety-first approach:
  - Backs up the full AD config before any changes
  - Processes one app at a time (configurable via limit)
  - Verifies each mapping was applied by re-fetching config
  - Skips apps that already have mapping entries
"""

import json
import os
from datetime import datetime

from veza_api import VezaAPI


def backup_ad_config(api: VezaAPI, ad_provider: dict) -> str:
    """
    Backup the current AD provider config before making changes.

    Saves a timestamped file in the daily folder and a 'latest' copy at the top level.

    Returns:
        Path to the timestamped backup file.
    """
    from steps import get_day_dir

    provider_id = ad_provider["id"]
    raw_providers = api.api_get("api/v1/providers/activedirectory")

    # Find the matching provider by ID
    full_config = None
    for p in raw_providers:
        if p["id"] == provider_id:
            full_config = p
            break

    if full_config is None:
        raise ValueError(f"AD provider {provider_id} not found in API response")

    day_dir = get_day_dir()
    timestamp = datetime.now().strftime("%H%M%S")
    timestamped_path = os.path.join(day_dir, f"ad_backup_{timestamp}.json")
    latest_path = os.path.join("output", "ad_backup_latest.json")

    os.makedirs("output", exist_ok=True)
    for path in (timestamped_path, latest_path):
        with open(path, "w") as f:
            json.dump(full_config, f, indent=2, default=str)

    return timestamped_path


def get_already_mapped_apps(ad_provider: dict) -> set[str]:
    """
    Parse existing identity mapping config and return set of already-mapped app names.

    Returns:
        Set of destination_datasource_oaa_app_type values for CUSTOM_APPLICATION entries.
    """
    config = ad_provider.get("identity_mapping_configuration")
    if not config:
        return set()

    mapped = set()
    for m in config.get("mappings", []):
        if m.get("destination_datasource_type") == "CUSTOM_APPLICATION":
            app_type = m.get("destination_datasource_oaa_app_type", "")
            if app_type:
                mapped.add(app_type)

    return mapped


def build_mapping_entry(app_name: str) -> dict:
    """
    Build a single CUSTOM_APPLICATION mapping entry.

    Args:
        app_name: The data source name (e.g., "Fraud Detection AI").

    Returns:
        Mapping entry dict matching the established pattern.
    """
    return {
        "destination_datasource_type": "CUSTOM_APPLICATION",
        "destination_datasource_oaa_app_type": app_name,
        "type": "EQUAL",
        "mode": "USERS",
        "transformations": [],
        "custom_value": "",
        "property_matchers": [
            {
                "source_property": "CUSTOM_PROPERTY",
                "destination_property": "CUSTOM_PROPERTY",
                "custom_source_property": "customprop_employee_number",
                "custom_destination_property": "customprop_user_id",
            }
        ],
        "id_matchers": [],
        "destination_datasources": [],
    }


def apply_single_mapping(
    api: VezaAPI, ad_provider: dict, app_name: str, dry_run: bool = False
) -> dict:
    """
    Apply a single mapping entry to the AD provider.

    Gets the current config, appends the new entry, and PATCHes the provider.

    Returns:
        Result dict with status, app_name, and response details.
    """
    provider_id = ad_provider["id"]
    new_entry = build_mapping_entry(app_name)

    # Fetch current config fresh to avoid stale state
    raw_providers = api.api_get("api/v1/providers/activedirectory")
    current_provider = None
    for p in raw_providers:
        if p["id"] == provider_id:
            current_provider = p
            break

    if current_provider is None:
        return {"status": "error", "app_name": app_name, "error": "Provider not found"}

    current_config = current_provider.get("identity_mapping_configuration", {})
    mappings = list(current_config.get("mappings", []))
    mappings.append(new_entry)

    updated_config = dict(current_config)
    updated_config["mappings"] = mappings

    if dry_run:
        return {
            "status": "dry_run",
            "app_name": app_name,
            "entry": new_entry,
        }

    patch_path = f"api/v1/providers/activedirectory/{provider_id}"
    patch_body = {"identity_mapping_configuration": updated_config}

    response = api.api_patch(patch_path, patch_body)

    return {
        "status": "applied",
        "app_name": app_name,
        "response_id": response.get("id", ""),
    }


def verify_mapping_applied(api: VezaAPI, ad_provider: dict, app_name: str) -> bool:
    """Check that a mapping entry for app_name now exists in the AD config."""
    raw_providers = api.api_get("api/v1/providers/activedirectory")
    for p in raw_providers:
        if p["id"] == ad_provider["id"]:
            config = p.get("identity_mapping_configuration", {})
            for m in config.get("mappings", []):
                if (
                    m.get("destination_datasource_type") == "CUSTOM_APPLICATION"
                    and m.get("destination_datasource_oaa_app_type") == app_name
                ):
                    return True
    return False


def apply_mappings(
    api: VezaAPI,
    ad_providers: list[dict],
    custom_apps: list[dict],
    limit: int = 1,
    dry_run: bool = False,
) -> dict:
    """
    Apply identity mappings for unmapped custom apps to the AD provider.

    Args:
        api: VezaAPI client instance.
        ad_providers: Output from step 1 (AD provider configs).
        custom_apps: Output from step 2 (custom app providers with data sources).
        limit: Max number of apps to map in this run (0 = all).
        dry_run: If True, don't actually PATCH — just show what would happen.

    Returns:
        Results dict with backup path, applied mappings, and summary.
    """
    from steps import get_day_dir

    # Use the first enabled AD provider
    enabled_ad = [p for p in ad_providers if p.get("state") == "ENABLED"]
    if not enabled_ad:
        print("  ERROR: No ENABLED AD providers found")
        return {"status": "error", "error": "No ENABLED AD providers"}

    ad_provider = enabled_ad[0]

    # Backup before any changes
    backup_path = backup_ad_config(api, ad_provider)
    print(f"  Backed up AD config to {backup_path}")

    # Determine what's already mapped
    already_mapped = get_already_mapped_apps(ad_provider)
    print(f"  Already mapped: {len(already_mapped)} apps ({', '.join(sorted(already_mapped))})")

    # Build list of apps that need mapping, using data source names
    apps_to_map = []
    for app in custom_apps:
        ds_list = app.get("data_sources", [])
        if not ds_list:
            continue
        ds_name = ds_list[0]["name"]
        if ds_name not in already_mapped:
            apps_to_map.append({"provider_name": app["name"], "ds_name": ds_name})

    print(f"  Remaining: {len(apps_to_map)} apps need mapping")

    if not apps_to_map:
        print("  Nothing to do — all apps are already mapped")
        return {"status": "complete", "applied": [], "already_mapped": len(already_mapped)}

    # Apply limit (0 = all)
    batch = apps_to_map if limit == 0 else apps_to_map[:limit]
    print(f"  Processing {len(batch)} of {len(apps_to_map)} (--limit {limit})")

    if dry_run:
        print("  DRY RUN — no changes will be made")

    results = []
    for i, app in enumerate(batch, 1):
        ds_name = app["ds_name"]
        print(f"    [{i}/{len(batch)}] Adding: {ds_name}...", end=" ", flush=True)

        result = apply_single_mapping(api, ad_provider, ds_name, dry_run=dry_run)

        if result["status"] == "applied":
            print("OK", end="", flush=True)
            # Verify
            if verify_mapping_applied(api, ad_provider, ds_name):
                print(" (verified)")
                result["verified"] = True
            else:
                print(" (WARNING: verification failed)")
                result["verified"] = False
        elif result["status"] == "dry_run":
            print("SKIPPED (dry run)")
        else:
            print(f"FAILED: {result.get('error', 'unknown')}")

        results.append(result)

    # Save results
    output = {
        "backup_path": backup_path,
        "dry_run": dry_run,
        "limit": limit,
        "already_mapped": len(already_mapped),
        "remaining_before": len(apps_to_map),
        "processed": len(batch),
        "results": results,
    }

    day_dir = get_day_dir()
    timestamp = datetime.now().strftime("%H%M%S")
    results_path = os.path.join(day_dir, f"step4_apply_results_{timestamp}.json")
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"  Results saved to {results_path}")

    return output

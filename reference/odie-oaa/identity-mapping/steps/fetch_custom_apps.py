"""
Step 2: Discover OAA custom application providers and their data sources.

Filtering strategy:
  - Current: Filter by external_id prefix (oaa_external:), custom_template,
    and state to identify ODIE-managed apps without relying on provider name prefix.
  - Future: When PROVIDER_PREFIX is set in the main pipeline, use --prefix
    to filter by provider name prefix instead.
"""

import json
import os

from veza_api import VezaAPI

# Providers to always exclude (not managed by ODIE pipeline)
EXCLUDE_NAMES = {
    "Windows Server",
    "Windows Files",
}


def fetch_custom_apps(
    api: VezaAPI,
    prefix_filter: str = None,
    oaa_only: bool = True,
) -> list[dict]:
    """
    Fetch custom application providers and their data sources.

    Args:
        api: VezaAPI client instance.
        prefix_filter: Filter by provider name prefix (e.g., "ODIE").
                       Future state: use PROVIDER_PREFIX from .env.
        oaa_only: If True (default), filter to ENABLED providers with
                  custom_template=application and external_id starting
                  with "oaa_external:". Excludes known non-ODIE providers.

    Returns:
        List of custom app providers, each with:
          - id, name, state, custom_template, external_id
          - data_sources: [{id, name}]
    """
    # Resolve prefix filter from env if not passed explicitly
    if prefix_filter is None:
        prefix_filter = os.getenv("PROVIDER_PREFIX")

    raw_providers = api.api_get("api/v1/providers/custom")
    total_count = len(raw_providers)

    # Apply prefix filter if set (future state)
    if prefix_filter:
        raw_providers = [
            p for p in raw_providers
            if p.get("name", "").startswith(prefix_filter)
        ]
        print(f"  Filtered to providers starting with '{prefix_filter}'")

    # Apply OAA filters (current approach)
    elif oaa_only:
        filtered = []
        excluded = []
        for p in raw_providers:
            name = p.get("name", "")
            state = p.get("state", "")
            template = p.get("custom_template", "")
            ext_id = p.get("external_id", "")

            if name in EXCLUDE_NAMES:
                excluded.append(f"{name} (excluded by name)")
                continue
            if state != "ENABLED":
                excluded.append(f"{name} ({state})")
                continue
            if template != "application":
                excluded.append(f"{name} (template: {template})")
                continue
            if not ext_id.startswith("oaa_external:"):
                excluded.append(f"{name} (external_id: {ext_id})")
                continue

            filtered.append(p)

        raw_providers = filtered
        if excluded:
            print(f"  Filtered: {len(raw_providers)} of {total_count} providers "
                  f"(excluded {len(excluded)}: DISABLED, non-application, non-OAA)")

    results = []
    total = len(raw_providers)
    print(f"  Fetching data sources for {total} providers...", end=" ", flush=True)
    for i, p in enumerate(raw_providers, 1):
        provider_id = p["id"]
        provider_name = p.get("name", "")

        # Fetch data sources for this provider
        ds_path = f"api/v1/providers/custom/{provider_id}/datasources"
        raw_datasources = api.api_get(ds_path)

        data_sources = [
            {"id": ds["id"], "name": ds.get("name", "")}
            for ds in raw_datasources
        ]

        results.append({
            "id": provider_id,
            "name": provider_name,
            "state": p.get("state", "UNKNOWN"),
            "custom_template": p.get("custom_template", ""),
            "external_id": p.get("external_id", ""),
            "data_sources": data_sources,
        })

        # Progress indicator every 10 providers
        if i % 10 == 0 or i == total:
            print(f"{i}/{total}", end=" ", flush=True)

    print()
    print(f"  Found {len(results)} custom application provider(s)")

    # Save output
    from steps import get_day_dir
    day_dir = get_day_dir()
    out_path = f"{day_dir}/step2_custom_apps.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Saved to {out_path}")

    return results

"""
Step 1: Fetch Active Directory provider integrations and their identity mapping state.
"""

import json

from veza_api import VezaAPI


def fetch_ad_config(api: VezaAPI) -> list[dict]:
    """
    Fetch all Active Directory providers from Veza.

    Returns list of AD providers, each with:
      - id, name, state
      - identity_mapping_configuration (null or {"attribute": "..."})
      - has_mapping, mapping_attribute (derived)
    """
    raw_providers = api.api_get("api/v1/providers/activedirectory")

    results = []
    for p in raw_providers:
        config = p.get("identity_mapping_configuration")
        results.append({
            "id": p["id"],
            "name": p["name"],
            "state": p.get("state", "UNKNOWN"),
            "identity_mapping_configuration": config,
            "has_mapping": config is not None,
            "mapping_attribute": config.get("attribute") if config else None,
        })

    print(f"  Found {len(results)} AD provider(s)")
    for r in results:
        status = "CONFIGURED" if r["has_mapping"] else "NOT_CONFIGURED"
        print(f"    - {r['name']} ({r['state']}) — mapping: {status}")

    # Save output
    from steps import get_day_dir
    day_dir = get_day_dir()
    out_path = f"{day_dir}/step1_ad_config.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Saved to {out_path}")

    return results

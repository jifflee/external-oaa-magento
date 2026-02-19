"""
Step 3: Build the identity mapping definition between AD (source) and
each OAA custom application (destination).
"""

import json
from datetime import datetime, timezone


def build_mapping(
    ad_providers: list[dict],
    custom_apps: list[dict],
    source_attribute: str = "email",
) -> dict:
    """
    Build identity mapping definition for each ENABLED AD provider x custom app.

    Args:
        ad_providers: Output from step 1 (AD provider configs).
        custom_apps: Output from step 2 (custom app providers).
        source_attribute: AD attribute for identity matching (default: email).

    Returns:
        Mapping report dict with ad_providers, custom_app_destinations,
        mapping_entries, and summary.
    """
    # Filter to enabled AD providers
    enabled_ad = [p for p in ad_providers if p.get("state") == "ENABLED"]
    if not enabled_ad:
        print("  Warning: No ENABLED AD providers found, using all providers")
        enabled_ad = ad_providers

    mapping_entries = []

    for ad in enabled_ad:
        current_config = ad.get("identity_mapping_configuration")
        is_configured = (
            current_config is not None
            and current_config.get("attribute") == source_attribute
        )

        for app in custom_apps:
            status = "CONFIGURED" if is_configured else "NOT_CONFIGURED"
            action = "none" if is_configured else "configure_identity_mapping"

            mapping_entries.append({
                "source": {
                    "type": "Active Directory",
                    "provider_id": ad["id"],
                    "provider_name": ad["name"],
                    "attribute": source_attribute,
                },
                "destination": {
                    "type": "OAA Custom Application",
                    "provider_id": app["id"],
                    "provider_name": app["name"],
                    "identity_field": "identities[]",
                },
                "status": status,
                "action_needed": action,
            })

    configured_count = sum(1 for m in mapping_entries if m["status"] == "CONFIGURED")
    not_configured_count = len(mapping_entries) - configured_count

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_attribute": source_attribute,
        "ad_providers": [
            {
                "id": ad["id"],
                "name": ad["name"],
                "state": ad.get("state", "UNKNOWN"),
                "current_mapping": ad.get("identity_mapping_configuration"),
                "status": "CONFIGURED" if ad.get("has_mapping") else "NOT_CONFIGURED",
            }
            for ad in enabled_ad
        ],
        "custom_app_destinations": [
            {
                "id": app["id"],
                "name": app["name"],
                "data_sources": app.get("data_sources", []),
            }
            for app in custom_apps
        ],
        "mapping_entries": mapping_entries,
        "summary": {
            "total_ad_providers": len(enabled_ad),
            "total_custom_apps": len(custom_apps),
            "total_mappings": len(mapping_entries),
            "configured": configured_count,
            "not_configured": not_configured_count,
        },
    }

    # Print human-readable table
    _print_mapping_table(mapping_entries)

    # Print summary
    print(f"\n  Summary: {configured_count} configured, "
          f"{not_configured_count} not configured, "
          f"{len(mapping_entries)} total mappings")

    # Save output
    from steps import get_day_dir
    day_dir = get_day_dir()
    out_path = f"{day_dir}/step3_identity_mapping.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Saved to {out_path}")

    return report


def _print_mapping_table(mapping_entries: list[dict]) -> None:
    """Print a human-readable mapping table to the console."""
    if not mapping_entries:
        print("  No mapping entries to display.")
        return

    # Column widths
    src_width = max(len(m["source"]["provider_name"]) for m in mapping_entries)
    src_width = max(src_width, len("SOURCE (AD)"))
    attr_width = max(len(m["source"]["attribute"]) for m in mapping_entries)
    attr_width = max(attr_width, len("ATTRIBUTE"))
    dst_width = max(len(m["destination"]["provider_name"]) for m in mapping_entries)
    dst_width = max(dst_width, len("DESTINATION (OAA)"))
    stat_width = max(len(m["status"]) for m in mapping_entries)
    stat_width = max(stat_width, len("STATUS"))

    # Header
    header = (
        f"  {'SOURCE (AD)':<{src_width}}    "
        f"{'ATTRIBUTE':<{attr_width}}      "
        f"{'DESTINATION (OAA)':<{dst_width}}    "
        f"{'STATUS':<{stat_width}}"
    )
    separator = (
        f"  {'─' * src_width}    "
        f"{'─' * attr_width}      "
        f"{'─' * dst_width}    "
        f"{'─' * stat_width}"
    )
    print()
    print(header)
    print(separator)

    # Rows
    for m in mapping_entries:
        src = m["source"]["provider_name"]
        attr = m["source"]["attribute"]
        dst = m["destination"]["provider_name"]
        status = m["status"]
        print(
            f"  {src:<{src_width}}    "
            f"{attr:<{attr_width}}  →   "
            f"{dst:<{dst_width}}    "
            f"{status:<{stat_width}}"
        )

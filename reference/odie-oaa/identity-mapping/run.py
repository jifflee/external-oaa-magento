"""
Identity Mapping Module — Main Entry Point

Automates the discovery and mapping of Active Directory identities
to OAA custom application providers in Veza.

Steps:
  1. Fetch AD provider integrations and their mapping state
  2. Discover all OAA custom application providers and data sources
  3. Build the identity mapping definition (source ↔ destination)
  4. (Optional) Apply identity mappings to the AD provider

Usage:
  python run.py                                      # Uses ../.env, discovers all
  python run.py --env ../../.env --debug              # Custom env path
  python run.py --prefix ODIE                         # Only ODIE_* providers (future)
  python run.py --no-filter                            # Include ALL custom providers
  python run.py --source-attribute userPrincipalName  # Different AD attribute
  python run.py --apply --limit 1                     # Apply 1 mapping
  python run.py --apply --limit 10                    # Apply 10 mappings
  python run.py --apply --limit 0                     # Apply all mappings
  python run.py --apply --limit 1 --dry-run           # Preview without changes
"""

import argparse
import json
import os
from datetime import datetime, timezone

from veza_api import VezaAPI
from steps import fetch_ad_config, fetch_custom_apps, build_mapping, apply_mappings, get_day_dir


def save_consolidated_report(
    ad_providers: list[dict],
    custom_apps: list[dict],
    mapping: dict,
) -> None:
    """Save a consolidated report combining all step outputs."""
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ad_providers": ad_providers,
        "custom_apps": custom_apps,
        "identity_mapping": mapping,
    }

    day_dir = get_day_dir()
    timestamp = datetime.now().strftime("%H%M%S")
    report_path = os.path.join(day_dir, f"consolidated_report_{timestamp}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nConsolidated report saved to {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Identity Mapping: AD ↔ OAA Custom Application"
    )
    parser.add_argument(
        "--env", default="../.env",
        help="Path to .env file (default: ../.env)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug output for API calls"
    )
    parser.add_argument(
        "--prefix", default=None,
        help="Filter custom apps by provider name prefix (e.g., ODIE)"
    )
    parser.add_argument(
        "--no-filter", action="store_true",
        help="Include ALL custom providers (skip OAA filtering)"
    )
    parser.add_argument(
        "--source-attribute", default="email",
        help="AD attribute for identity matching (default: email)"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply identity mappings to AD provider"
    )
    parser.add_argument(
        "--limit", type=int, default=1,
        help="Max apps to map per run (default: 1)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without applying them"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Identity Mapping: AD ↔ OAA Custom Applications")
    print("=" * 60)

    api = VezaAPI(env_file=args.env, debug=args.debug)

    # Step 1
    print("\nSTEP 1: Fetching AD configurations...")
    ad_providers = fetch_ad_config(api)

    # Step 2
    print("\nSTEP 2: Fetching custom application providers...")
    custom_apps = fetch_custom_apps(
        api, prefix_filter=args.prefix, oaa_only=not args.no_filter
    )

    # Step 3
    print("\nSTEP 3: Building identity mapping definition...")
    mapping = build_mapping(
        ad_providers, custom_apps, source_attribute=args.source_attribute
    )

    # Save consolidated report
    save_consolidated_report(ad_providers, custom_apps, mapping)

    # Step 4 (optional)
    if args.apply:
        print("\nSTEP 4: Applying identity mappings...")
        apply_mappings(
            api, ad_providers, custom_apps,
            limit=args.limit, dry_run=args.dry_run,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()

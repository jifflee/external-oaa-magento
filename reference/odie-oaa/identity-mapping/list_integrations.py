"""
List all active integrations with creation timestamps.

Queries all provider types (custom, AD, Azure, etc.) and displays
a consolidated table with state and data source timestamps.

Usage:
  python list_integrations.py                  # All active integrations
  python list_integrations.py --all            # Include disabled
  python list_integrations.py --type custom    # Only custom providers
  python list_integrations.py --json           # Save full results to JSON
"""

import argparse
import json
import os
from datetime import datetime

from veza_api import VezaAPI
from steps import get_day_dir


# Known provider type endpoints
PROVIDER_TYPES = {
    "custom": "api/v1/providers/custom",
    "activedirectory": "api/v1/providers/activedirectory",
    "azure_ad": "api/v1/providers/azure_ad",
    "okta": "api/v1/providers/okta",
    "aws": "api/v1/providers/aws",
    "gcp": "api/v1/providers/gcp",
    "github": "api/v1/providers/github",
    "salesforce": "api/v1/providers/salesforce",
    "snowflake": "api/v1/providers/snowflake",
    "sql_server": "api/v1/providers/sql_server",
    "oracle": "api/v1/providers/oracle_database",
    "onelogin": "api/v1/providers/onelogin",
    "csv_upload": "api/v1/providers/csv_upload",
    "crowdstrike": "api/v1/providers/crowdstrike",
    "bitbucket": "api/v1/providers/bitbucket",
    "google_workspace": "api/v1/providers/google_workspace",
}


def fetch_all_integrations(api: VezaAPI, provider_type: str = None, include_disabled: bool = False) -> list[dict]:
    """Fetch integrations across all provider types with data source timestamps."""
    results = []

    types_to_query = PROVIDER_TYPES
    if provider_type:
        if provider_type not in PROVIDER_TYPES:
            print(f"  Unknown type '{provider_type}'. Available: {', '.join(sorted(PROVIDER_TYPES))}")
            return results
        types_to_query = {provider_type: PROVIDER_TYPES[provider_type]}

    for ptype, endpoint in sorted(types_to_query.items()):
        try:
            providers = api.api_get(endpoint)
        except Exception:
            # Endpoint doesn't exist or no access — skip silently
            continue

        if not providers:
            continue

        for p in providers:
            state = p.get("state", "UNKNOWN")
            if not include_disabled and state != "ENABLED":
                continue

            # For custom providers, fetch data source timestamps
            ds_created = None
            ds_updated = None
            ds_pushed = None
            ds_count = 0

            if ptype == "custom":
                try:
                    ds_path = f"api/v1/providers/custom/{p['id']}/datasources"
                    data_sources = api.api_get(ds_path)
                    ds_count = len(data_sources)
                    if data_sources:
                        # Use the earliest created_at across data sources
                        created_dates = [ds.get("created_at") for ds in data_sources if ds.get("created_at")]
                        updated_dates = [ds.get("updated_at") for ds in data_sources if ds.get("updated_at")]
                        pushed_dates = [ds.get("pushed_at") for ds in data_sources if ds.get("pushed_at")]
                        if created_dates:
                            ds_created = min(created_dates)
                        if updated_dates:
                            ds_updated = max(updated_dates)
                        if pushed_dates:
                            ds_pushed = max(pushed_dates)
                except Exception:
                    pass

            results.append({
                "type": ptype,
                "name": p.get("name", ""),
                "id": p.get("id", ""),
                "state": state,
                "data_sources": ds_count,
                "created_at": ds_created,
                "updated_at": ds_updated,
                "pushed_at": ds_pushed,
            })

    return results


def print_table(integrations: list[dict]) -> None:
    """Print integrations as a formatted table sorted by creation date."""
    if not integrations:
        print("  No integrations found.")
        return

    # Sort: integrations with timestamps first (oldest first), then those without
    def sort_key(r):
        if r["created_at"]:
            return (0, r["created_at"])
        return (1, r["name"])

    integrations.sort(key=sort_key)

    # Column widths
    type_w = max(len(r["type"]) for r in integrations)
    type_w = max(type_w, len("TYPE"))
    name_w = min(max(len(r["name"]) for r in integrations), 45)
    name_w = max(name_w, len("NAME"))

    header = (
        f"  {'#':<4} {'TYPE':<{type_w}}  {'NAME':<{name_w}}  "
        f"{'STATE':<8}  {'DS':<3}  {'CREATED':<20}  {'LAST UPDATED':<20}  {'LAST PUSHED':<20}"
    )
    sep = (
        f"  {'─'*4} {'─'*type_w}  {'─'*name_w}  "
        f"{'─'*8}  {'─'*3}  {'─'*20}  {'─'*20}  {'─'*20}"
    )

    print()
    print(header)
    print(sep)

    for i, r in enumerate(integrations, 1):
        name = r["name"][:name_w]
        created = (r["created_at"] or "—")[:20]
        updated = (r["updated_at"] or "—")[:20]
        pushed = (r["pushed_at"] or "—")[:20]
        ds = str(r["data_sources"]) if r["data_sources"] else "—"

        print(
            f"  {i:<4} {r['type']:<{type_w}}  {name:<{name_w}}  "
            f"{r['state']:<8}  {ds:<3}  {created:<20}  {updated:<20}  {pushed:<20}"
        )

    print()
    print(f"  Total: {len(integrations)} active integration(s)")


def main():
    parser = argparse.ArgumentParser(description="List all active Veza integrations with timestamps")
    parser.add_argument("--env", default="../.env", help="Path to .env file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--all", action="store_true", help="Include disabled integrations")
    parser.add_argument("--type", default=None, help=f"Filter by type: {', '.join(sorted(PROVIDER_TYPES))}")
    parser.add_argument("--json", action="store_true", help="Save results to JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("Active Integrations Report")
    print("=" * 60)

    api = VezaAPI(env_file=args.env, debug=args.debug)

    print("\nFetching integrations...", end=" ", flush=True)
    integrations = fetch_all_integrations(api, provider_type=args.type, include_disabled=args.all)
    print(f"found {len(integrations)}")

    print_table(integrations)

    if args.json:
        day_dir = get_day_dir()
        out_path = os.path.join(day_dir, "active_integrations.json")
        with open(out_path, "w") as f:
            json.dump(integrations, f, indent=2, default=str)
        print(f"  Saved to {out_path}")


if __name__ == "__main__":
    main()

"""
Debug script: Dump full raw API responses for custom providers.

Pulls the first few providers with ALL fields so we can see what's
available for filtering.

Usage:
  python debug_raw_response.py              # First 3 providers
  python debug_raw_response.py --count 10   # First 10 providers
  python debug_raw_response.py --count 0    # All providers (headers only)
"""

import argparse
import json
import os
from datetime import datetime

from veza_api import VezaAPI
from steps import get_day_dir


def main():
    parser = argparse.ArgumentParser(description="Dump raw custom provider API responses")
    parser.add_argument("--env", default="../.env", help="Path to .env file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--count", type=int, default=3, help="Number of providers to dump fully (0 = all, just keys)")
    args = parser.parse_args()

    api = VezaAPI(env_file=args.env, debug=args.debug)

    # Fetch raw providers — full response, no field stripping
    print("\nFetching raw custom providers...")
    raw_providers = api.api_get("api/v1/providers/custom")
    print(f"  Total providers: {len(raw_providers)}")

    if not raw_providers:
        print("  No providers found.")
        return

    # Show all available keys from first provider
    first = raw_providers[0]
    print(f"\n  Available fields on provider object:")
    for key in sorted(first.keys()):
        val = first[key]
        val_type = type(val).__name__
        preview = repr(val)[:80] if not isinstance(val, (dict, list)) else f"<{val_type}>"
        print(f"    {key}: {preview}")

    # Dump full details for --count providers (skip data source fetch when 0)
    if args.count > 0:
        limit = min(args.count, len(raw_providers))
        sample = raw_providers[:limit]

        # Fetch data sources only for the sample
        for p in sample:
            ds_path = f"api/v1/providers/custom/{p['id']}/datasources"
            p["_raw_data_sources"] = api.api_get(ds_path)

        day_dir = get_day_dir()
        out_path = os.path.join(day_dir, "debug_raw_custom_providers.json")
        with open(out_path, "w") as f:
            json.dump(sample, f, indent=2, default=str)

        print(f"\n  Dumped {limit} full provider(s) to {out_path}")

    # Filter: ENABLED + custom_template=application
    targets = [
        p for p in raw_providers
        if p.get("state") == "ENABLED" and p.get("custom_template") == "application"
    ]
    others = [p for p in raw_providers if p not in targets]

    print(f"\n  ENABLED + custom_template=application: {len(targets)} providers")
    print(f"  {'#':<4} {'NAME':<40} {'EXTERNAL_ID':<50}")
    print(f"  {'─'*4} {'─'*40} {'─'*50}")
    for i, p in enumerate(targets, 1):
        name = p.get("name", "")[:40]
        ext_id = p.get("external_id", "")[:50]
        print(f"  {i:<4} {name:<40} {ext_id:<50}")

    if others:
        print(f"\n  EXCLUDED ({len(others)} providers):")
        print(f"  {'NAME':<40} {'STATE':<10} {'CUSTOM_TEMPLATE':<20} {'EXTERNAL_ID':<50}")
        print(f"  {'─'*40} {'─'*10} {'─'*20} {'─'*50}")
        for p in others:
            name = p.get("name", "")[:40]
            state = p.get("state", "?")
            template = p.get("custom_template", "?")
            ext_id = p.get("external_id", "?")[:50]
            print(f"  {name:<40} {state:<10} {template:<20} {ext_id:<50}")

    # Save target list to daily output
    day_dir = get_day_dir()
    target_list = [
        {"id": p["id"], "name": p["name"], "custom_template": p.get("custom_template"), "state": p.get("state")}
        for p in targets
    ]
    out_path = os.path.join(day_dir, "rename_candidates.json")
    with open(out_path, "w") as f:
        json.dump(target_list, f, indent=2)
    print(f"\n  Saved {len(targets)} rename candidates to {out_path}")


if __name__ == "__main__":
    main()

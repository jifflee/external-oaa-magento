"""
Rename custom application providers to add ODIE_ prefix.

Safety-first approach:
  - Backs up all provider names before any changes
  - Processes one at a time (configurable via --limit)
  - Validates each rename by re-fetching the provider
  - Skips providers that already have the prefix
  - Dry-run mode to preview changes without applying

Targets: ENABLED providers with custom_template=application
Excludes: Windows Server, non-application templates, DISABLED providers

Usage:
  python rename_providers.py --dry-run              # Preview all renames
  python rename_providers.py --limit 1              # Rename 1 provider
  python rename_providers.py --limit 5              # Rename 5 providers
  python rename_providers.py --limit 0              # Rename all (use with caution)
"""

import argparse
import json
import os
from datetime import datetime

from veza_api import VezaAPI
from steps import get_day_dir

PREFIX = "ODIE_"

# Providers to skip (not part of our ODIE pipeline)
EXCLUDE_NAMES = {
    "Windows Server",
    "Windows Files",
    "CyberArk",
    "CyberArk SG",
    "DIAMAR",
    "PEOPLE",
}


def fetch_rename_candidates(api: VezaAPI) -> list[dict]:
    """
    Fetch all custom providers and filter to rename candidates.

    Criteria:
      - state == ENABLED
      - custom_template == application
      - name not in EXCLUDE_NAMES
      - name does not already start with PREFIX
    """
    raw_providers = api.api_get("api/v1/providers/custom")

    candidates = []
    skipped_prefix = []
    skipped_excluded = []
    skipped_other = []

    for p in raw_providers:
        name = p.get("name", "")
        state = p.get("state", "")
        template = p.get("custom_template", "")

        if name in EXCLUDE_NAMES:
            skipped_excluded.append(name)
            continue

        if state != "ENABLED" or template != "application":
            skipped_other.append(f"{name} ({state}/{template})")
            continue

        if name.startswith(PREFIX):
            skipped_prefix.append(name)
            continue

        candidates.append({
            "id": p["id"],
            "current_name": name,
            "new_name": f"{PREFIX}{name}",
        })

    print(f"  Rename candidates: {len(candidates)}")
    print(f"  Already prefixed (skipped): {len(skipped_prefix)}")
    print(f"  Excluded by name: {len(skipped_excluded)}")
    if skipped_other:
        print(f"  Excluded (disabled/non-app): {len(skipped_other)}")

    return candidates


def backup_provider_names(candidates: list[dict]) -> str:
    """Save the current provider names to a backup file before renaming."""
    day_dir = get_day_dir()
    timestamp = datetime.now().strftime("%H%M%S")
    backup_path = os.path.join(day_dir, f"rename_backup_{timestamp}.json")

    backup = {
        "created_at": datetime.now().isoformat(),
        "prefix": PREFIX,
        "providers": candidates,
    }

    with open(backup_path, "w") as f:
        json.dump(backup, f, indent=2)

    # Also save latest for easy rollback
    latest_path = os.path.join("output", "rename_backup_latest.json")
    os.makedirs("output", exist_ok=True)
    with open(latest_path, "w") as f:
        json.dump(backup, f, indent=2)

    return backup_path


def rename_single_provider(api: VezaAPI, provider_id: str, new_name: str) -> dict:
    """
    Rename a single provider via PATCH.

    Returns:
        API response dict.
    """
    patch_path = f"api/v1/providers/custom/{provider_id}"
    return api.api_patch(patch_path, {"name": new_name})


def validate_rename(api: VezaAPI, provider_id: str, expected_name: str) -> bool:
    """Re-fetch the provider and confirm the name matches."""
    raw_providers = api.api_get("api/v1/providers/custom")
    for p in raw_providers:
        if p["id"] == provider_id:
            return p.get("name") == expected_name
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Rename custom app providers to add ODIE_ prefix"
    )
    parser.add_argument("--env", default="../.env", help="Path to .env file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument(
        "--limit", type=int, default=1,
        help="Max providers to rename per run (default: 1, 0 = all)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without applying them"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Provider Rename: Add ODIE_ Prefix")
    print("=" * 60)

    api = VezaAPI(env_file=args.env, debug=args.debug)

    # Fetch candidates
    print("\nFetching rename candidates...")
    candidates = fetch_rename_candidates(api)

    if not candidates:
        print("\n  Nothing to rename — all providers already have the prefix or are excluded.")
        return

    # Show preview
    print(f"\n  Preview (showing first {min(10, len(candidates))} of {len(candidates)}):")
    print(f"  {'#':<4} {'CURRENT NAME':<40} {'NEW NAME':<45}")
    print(f"  {'─'*4} {'─'*40} {'─'*45}")
    for i, c in enumerate(candidates[:10], 1):
        print(f"  {i:<4} {c['current_name']:<40} {c['new_name']:<45}")
    if len(candidates) > 10:
        print(f"  ... and {len(candidates) - 10} more")

    if args.dry_run:
        print(f"\n  DRY RUN — no changes made. {len(candidates)} providers would be renamed.")
        # Save full preview
        day_dir = get_day_dir()
        preview_path = os.path.join(day_dir, "rename_preview.json")
        with open(preview_path, "w") as f:
            json.dump(candidates, f, indent=2)
        print(f"  Full preview saved to {preview_path}")
        return

    # Backup
    backup_path = backup_provider_names(candidates)
    print(f"\n  Backed up {len(candidates)} provider names to {backup_path}")

    # Apply limit
    batch = candidates if args.limit == 0 else candidates[:args.limit]
    print(f"\n  Processing {len(batch)} of {len(candidates)} (--limit {args.limit})")

    results = []
    success_count = 0
    fail_count = 0

    for i, c in enumerate(batch, 1):
        current = c["current_name"]
        new = c["new_name"]
        provider_id = c["id"]

        print(f"    [{i}/{len(batch)}] {current} → {new}...", end=" ", flush=True)

        try:
            rename_single_provider(api, provider_id, new)
            print("OK", end="", flush=True)

            # Validate
            if validate_rename(api, provider_id, new):
                print(" (verified)")
                results.append({"id": provider_id, "old": current, "new": new, "status": "success", "verified": True})
                success_count += 1
            else:
                print(" (WARNING: verification failed)")
                results.append({"id": provider_id, "old": current, "new": new, "status": "success", "verified": False})
                success_count += 1
        except Exception as e:
            print(f"FAILED: {e}")
            results.append({"id": provider_id, "old": current, "new": new, "status": "error", "error": str(e)})
            fail_count += 1

    # Save results
    day_dir = get_day_dir()
    timestamp = datetime.now().strftime("%H%M%S")
    results_output = {
        "timestamp": datetime.now().isoformat(),
        "prefix": PREFIX,
        "limit": args.limit,
        "total_candidates": len(candidates),
        "processed": len(batch),
        "success": success_count,
        "failed": fail_count,
        "remaining": len(candidates) - len(batch),
        "results": results,
    }

    results_path = os.path.join(day_dir, f"rename_results_{timestamp}.json")
    with open(results_path, "w") as f:
        json.dump(results_output, f, indent=2)

    print(f"\n  Summary: {success_count} renamed, {fail_count} failed, {len(candidates) - len(batch)} remaining")
    print(f"  Results saved to {results_path}")


if __name__ == "__main__":
    main()

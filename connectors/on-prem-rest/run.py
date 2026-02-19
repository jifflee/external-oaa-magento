#!/usr/bin/env python3
"""
Magento B2B On-Prem REST Connector - Extract B2B authorization data via REST API.

Usage:
    python run.py --dry-run                    # Extract and save JSON only
    python run.py --push                       # Extract and push to Veza
    python run.py --debug                      # Enable debug output
    python run.py --strategy csv_supplement    # Use CSV user-role mapping
"""

import sys
import argparse

from core import RESTOrchestrator


def main():
    parser = argparse.ArgumentParser(
        description="Magento B2B On-Prem REST Connector - Extract authorization data for Veza"
    )
    parser.add_argument("--env", "-e", default="./.env", help="Path to .env file")
    parser.add_argument("--dry-run", action="store_true", help="Generate JSON only (no push)")
    parser.add_argument("--push", action="store_true", help="Push to Veza")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument(
        "--strategy",
        choices=["default_role", "csv_supplement", "all_roles", "skip"],
        help="User-role gap workaround strategy",
    )

    args = parser.parse_args()

    orchestrator = RESTOrchestrator(env_file=args.env)

    if args.dry_run:
        orchestrator.dry_run = True
    if args.push:
        orchestrator.dry_run = False
    if args.debug:
        orchestrator.debug = True
    if args.strategy:
        orchestrator.user_role_strategy = args.strategy

    print(f"\n{'='*60}")
    print("MAGENTO B2B ON-PREM REST CONNECTOR")
    print("="*60)
    print(f"Mode: {'DRY RUN' if orchestrator.dry_run else 'LIVE PUSH'}")
    print(f"Store: {orchestrator.store_url}")
    print(f"User-Role Strategy: {orchestrator.user_role_strategy}")

    if not orchestrator.validate_config():
        sys.exit(1)

    if orchestrator.output_manager.retention_days > 0:
        deleted = orchestrator.output_manager.cleanup_old_folders(orchestrator.debug)
        if deleted > 0:
            print(f"Cleaned up {deleted} old output folder(s)")

    results = orchestrator.run()
    orchestrator.print_summary(results)

    if not results.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()

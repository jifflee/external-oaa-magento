#!/usr/bin/env python3
"""
COMMERCE CLOUD GRAPHQL CONNECTOR - Extract B2B authorization data via GraphQL.

Authenticates via Adobe IMS OAuth (client_credentials) instead of customer
username/password. Designed for Adobe Commerce Cloud (SaaS) deployments.

Usage:
    python run.py --dry-run          # Extract and save JSON only
    python run.py --push             # Extract and push to Veza
    python run.py --debug            # Enable debug output
    python run.py --no-rest          # Skip REST role supplement
"""

import sys
import argparse

from core import CloudGraphQLOrchestrator


def main():
    parser = argparse.ArgumentParser(
        description="Commerce Cloud GraphQL Connector - Extract authorization data for Veza"
    )
    parser.add_argument("--env", "-e", default="./.env", help="Path to .env file")
    parser.add_argument("--dry-run", action="store_true", help="Generate JSON only (no push)")
    parser.add_argument("--push", action="store_true", help="Push to Veza")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-rest", action="store_true", help="Skip REST role supplement")

    args = parser.parse_args()

    # Initialize
    orchestrator = CloudGraphQLOrchestrator(env_file=args.env)

    # Apply CLI overrides
    if args.dry_run:
        orchestrator.dry_run = True
    if args.push:
        orchestrator.dry_run = False
    if args.debug:
        orchestrator.debug = True
    if args.no_rest:
        orchestrator.use_rest_supplement = False

    # Print header
    print(f"\n{'='*60}")
    print("COMMERCE CLOUD GRAPHQL CONNECTOR")
    print("="*60)
    print(f"Mode: {'DRY RUN' if orchestrator.dry_run else 'LIVE PUSH'}")
    print(f"Store: {orchestrator.store_url}")
    print(f"REST Supplement: {'Enabled' if orchestrator.use_rest_supplement else 'Disabled'}")

    # Validate configuration
    if not orchestrator.validate_config():
        sys.exit(1)

    # Cleanup old output
    if orchestrator.output_manager.retention_days > 0:
        deleted = orchestrator.output_manager.cleanup_old_folders(orchestrator.debug)
        if deleted > 0:
            print(f"Cleaned up {deleted} old output folder(s)")

    # Run pipeline
    results = orchestrator.run()

    # Print summary
    orchestrator.print_summary(results)

    # Exit with error code if failed
    if not results.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()

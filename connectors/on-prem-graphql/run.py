#!/usr/bin/env python3
"""
Magento B2B GraphQL Extractor - Extract B2B authorization data via GraphQL.

Usage:
    python run.py               # Extract and save JSON
    python run.py --debug        # Verbose output
    python run.py --no-rest      # Skip REST role supplement
    python run.py --version      # Show version
"""

import sys
import argparse
from pathlib import Path

from core import GraphQLOrchestrator

VERSION_FILE = Path(__file__).resolve().parent.parent.parent / "VERSION"
VERSION = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "unknown"


def main():
    parser = argparse.ArgumentParser(
        description="Magento B2B GraphQL Extractor - Extract authorization data from Adobe Commerce"
    )
    parser.add_argument("--env", "-e", default="./.env", help="Path to .env file")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--no-rest", action="store_true", help="Skip REST role supplement")
    parser.add_argument("--version", "-v", action="store_true", help="Show version and exit")

    args = parser.parse_args()

    if args.version:
        print(f"magento-b2b-extractor {VERSION}")
        sys.exit(0)

    # Initialize
    orchestrator = GraphQLOrchestrator(env_file=args.env)

    # Apply overrides
    if args.debug:
        orchestrator.debug = True
    if args.no_rest:
        orchestrator.use_rest_supplement = False

    # Print header
    print(f"\n{'='*60}")
    print(f"MAGENTO B2B GRAPHQL EXTRACTOR v{VERSION}")
    print("="*60)
    print(f"Store: {orchestrator.store_url}")
    print(f"REST Supplement: {'Enabled' if orchestrator.use_rest_supplement else 'Disabled'}")

    # Validate
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

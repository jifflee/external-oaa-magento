#!/usr/bin/env python3
"""
Magento B2B Authorization Data Extractor — Entry Point.

This is the main script that users run to extract B2B authorization data from
an Adobe Commerce (Magento) instance. It reads configuration from a .env file,
initializes the GraphQL extraction pipeline, and saves structured JSON output.

The extraction pipeline (managed by GraphQLOrchestrator) performs 7 steps:
  1. Authenticate with Magento via REST token endpoint
  2. Execute a single GraphQL query to retrieve the full company structure
  3. Optionally fetch per-role ACL permissions via REST supplement
  4. Parse the GraphQL response into normalized entities
  5. Build a Veza OAA CustomApplication data structure
  6. Wire all entity relationships (user→role, role→permission, etc.)
  7. Save the output as timestamped JSON files

Usage:
    python run.py               # Extract and save JSON
    python run.py --debug       # Verbose output
    python run.py --no-rest     # Skip REST role supplement
    python run.py --version     # Show version
    python run.py --env /path   # Use alternate .env file
"""

import sys
import argparse
from pathlib import Path

from core import GraphQLOrchestrator

# Read version from the repo-root VERSION file (e.g., "0.1.0").
# This keeps the version in one place for the whole repository.
VERSION_FILE = Path(__file__).resolve().parent.parent.parent / "VERSION"
VERSION = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else "unknown"


def main():
    """Parse CLI arguments and run the extraction pipeline."""
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

    # Initialize the orchestrator (loads .env and builds internal config)
    orchestrator = GraphQLOrchestrator(env_file=args.env)

    # Apply CLI overrides on top of .env values
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

    # Validate required configuration before proceeding
    if not orchestrator.validate_config():
        sys.exit(1)

    # Cleanup old output folders based on retention policy
    if orchestrator.output_manager.retention_days > 0:
        deleted = orchestrator.output_manager.cleanup_old_folders(orchestrator.debug)
        if deleted > 0:
            print(f"Cleaned up {deleted} old output folder(s)")

    # Run the 7-step extraction pipeline
    results = orchestrator.run()

    # Print final summary
    orchestrator.print_summary(results)

    # Exit with error code if extraction failed
    if not results.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
================================================================================
ODIE-OAA CONNECTOR - Main Entry Point
================================================================================

USAGE:
    python run.py --dry-run                    # Generate JSON, check for conflicts
    python run.py --csv ./data/mydata.csv      # Use specific CSV file
    python run.py --push                       # Push to Veza (interactive conflict resolution)
    python run.py --push --skip-existing       # Push, skip existing providers
    python run.py --push --delete-existing     # Push, delete & recreate existing
    python run.py --validate-only              # Only run identity mapping validation
    python run.py --debug                      # Enable debug output

CONFLICT RESOLUTION:
    The connector runs a preflight check to detect existing providers in Veza.
    If conflicts are found:
    1. Add PROVIDER_PREFIX=ODIE to .env (recommended - adds prefix to all names)
    2. Use --skip-existing to skip conflicting applications
    3. Use --delete-existing to delete and recreate providers
    4. Rename applications in your CSV file

POST-DEPLOYMENT VALIDATION:
    After pushing to Veza, the connector validates identity mapping configuration.
    Without identity mapping, OAA users will NOT link to IdP identities in the graph.

    If validation fails:
    1. Configure identity mapping in Veza UI (Integrations > Active Directory > Edit)
    2. Run: python run.py --validate-only    # Re-check after configuration

For configuration customization, see the config/ directory:
    config/settings.py     - Known permissions and defaults
    config/roles.py        - Role definitions and mappings
    config/permissions.py  - Base permission definitions

================================================================================
"""

import sys
import argparse
import json
import logging

from core import MultiSourceOrchestrator


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ODIE-OAA Connector - Process CSV permission data for Veza"
    )
    parser.add_argument("--env", "-e", default="./.env", help="Path to .env file")
    parser.add_argument("--csv", "-c", help="Override CSV input path")
    parser.add_argument("--dry-run", action="store_true", help="Generate JSON only (no push)")
    parser.add_argument("--push", action="store_true", help="Push to Veza")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    # Post-deployment validation options
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run identity mapping validation (re-check after configuration)"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip post-deployment identity mapping validation"
    )
    parser.add_argument(
        "--idp-type",
        default="activedirectory",
        choices=["activedirectory"],
        help="Identity provider type to validate (default: activedirectory)"
    )

    # Preflight conflict handling options
    conflict_group = parser.add_mutually_exclusive_group()
    conflict_group.add_argument(
        "--skip-existing",
        action="store_true",
        help="Automatically skip applications with existing providers"
    )
    conflict_group.add_argument(
        "--delete-existing",
        action="store_true",
        help="Automatically delete and recreate existing providers"
    )

    args = parser.parse_args()

    # Enable debug logging for oaaclient if --debug flag is set
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(name)s - %(levelname)s - %(message)s'
        )
        # Enable debug on oaaclient specifically
        logging.getLogger('oaaclient').setLevel(logging.DEBUG)

    # Initialize
    orchestrator = MultiSourceOrchestrator(env_file=args.env)

    # Apply overrides
    if args.csv:
        orchestrator.csv_input_path = args.csv
    if args.dry_run:
        orchestrator.dry_run = True
    if args.push:
        orchestrator.dry_run = False
    if args.debug:
        orchestrator.debug = True

    # Print header
    print(f"\n{'='*60}")
    print("ODIE-OAA CONNECTOR")
    print('='*60)
    print(f"Mode: {'DRY RUN' if orchestrator.dry_run else 'LIVE PUSH'}")
    print(f"CSV: {orchestrator.csv_input_path}")
    if orchestrator.provider_prefix:
        print(f"Provider Prefix: {orchestrator.provider_prefix}_")

    # Show proxy configuration if set
    orchestrator.print_proxy_status()

    # Handle --validate-only mode
    if args.validate_only:
        print(f"\n{'='*60}")
        print("VALIDATE-ONLY MODE")
        print('='*60)
        print("Re-checking identity mapping configuration...")

        validation_result = orchestrator.revalidate_identity_mapping(idp_type=args.idp_type)

        if validation_result.get("validation_passed"):
            print("\nIdentity mapping validation PASSED.")
            sys.exit(0)
        else:
            print("\nIdentity mapping validation FAILED - see recommendations above.")
            sys.exit(1)

    # Validate
    if not orchestrator.validate_config():
        sys.exit(1)

    # Cleanup old output
    if orchestrator.output_manager.retention_days > 0:
        deleted = orchestrator.output_manager.cleanup_old_folders(orchestrator.debug)
        if deleted > 0:
            print(f"Cleaned up {deleted} old output folder(s)")

    # Preflight check - always run to catch conflicts early
    preflight_result = None
    auto_mode = None
    if args.skip_existing:
        auto_mode = "skip"
    elif args.delete_existing:
        auto_mode = "delete"

    preflight_result = orchestrator.preflight_check(
        auto_mode=auto_mode,
        dry_run_check=orchestrator.dry_run
    )

    if not preflight_result.get("proceed", True):
        print("\nOperation aborted.")
        sys.exit(0)

    # In dry-run mode with conflicts, warn but continue to generate JSON
    if orchestrator.dry_run and preflight_result.get("has_conflicts"):
        print("\n  NOTE: Resolve conflicts above before running with --push")

    # Process
    results = orchestrator.process_all_applications(preflight_result=preflight_result)

    # Summary
    orchestrator.print_summary(results)

    # Save results
    results_path = orchestrator.save_results(results)
    print(f"\nResults saved to: {results_path}")

    # Post-deployment validation (only for live push mode)
    if not orchestrator.dry_run and not args.skip_validation:
        successful = results.get("summary", {}).get("successful", 0)
        if successful > 0:
            print(f"\n{'='*60}")
            print("POST-DEPLOYMENT VALIDATION")
            print('='*60)

            validation_result = orchestrator.validate_identity_mapping(
                idp_type=args.idp_type,
                save_results=True
            )

            # Store validation result in results for reference
            results["identity_mapping_validation"] = {
                "passed": validation_result.get("validation_passed", False),
                "has_mapping": validation_result.get("has_identity_mapping", False),
                "issues": validation_result.get("issues", [])
            }

            # Re-save results with validation info
            with open(results_path, 'w') as f:
                json.dump(results, f, indent=2, default=str)

            if not validation_result.get("validation_passed"):
                print("\n  NOTE: Identity mapping is not configured.")
                print("  Graph relationships will NOT work until configured.")
                print("  After configuring in Veza UI, run: python run.py --validate-only")

    # Exit with error code if any failures
    if results.get("summary", {}).get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

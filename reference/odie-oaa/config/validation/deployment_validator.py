#!/usr/bin/env python3
"""
================================================================================
DEPLOYMENT VALIDATOR - Post-Deployment Identity Mapping Validation
================================================================================

PURPOSE:
    Re-exports the DeploymentValidator from core for use in config/validation.

    The actual implementation lives in core/deployment_validator.py - this is
    just a convenience wrapper for the config module structure.

USAGE:
    python -m config.validation.deployment_validator                # Check all OAA apps
    python -m config.validation.deployment_validator --provider-prefix ODIE
    python -m config.validation.deployment_validator --revalidate
    python -m config.validation.deployment_validator --save

================================================================================
"""

import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv

# Re-export from core
from core.deployment_validator import DeploymentValidator

__all__ = ['DeploymentValidator']


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Post-Deployment Validation - Check identity mapping configuration"
    )
    parser.add_argument("--env", "-e", default="./.env", help="Path to .env file")
    parser.add_argument(
        "--idp-type",
        choices=["activedirectory"],
        default="activedirectory",
        help="Identity provider type to check (default: activedirectory)"
    )
    parser.add_argument(
        "--provider-prefix",
        help="Filter OAA providers by prefix (e.g., ODIE)"
    )
    parser.add_argument(
        "--revalidate",
        action="store_true",
        help="Re-check if previous validation failed"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results and provider IDs to output folder"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )

    args = parser.parse_args()

    # Load .env
    env_path = Path(args.env)
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded configuration from: {args.env}")
    else:
        print(f"Warning: {args.env} not found, using environment variables")

    # Get configuration
    veza_url = os.getenv("VEZA_URL", "")
    veza_api_key = os.getenv("VEZA_API_KEY", "")
    output_dir = os.getenv("OUTPUT_DIR", "./output")
    provider_prefix = args.provider_prefix or os.getenv("PROVIDER_PREFIX", "")

    # Print header
    print(f"\n{'='*60}")
    print("ODIE-OAA POST-DEPLOYMENT VALIDATOR")
    print('='*60)

    # Validate configuration
    if not veza_url:
        print("\nError: VEZA_URL is required")
        sys.exit(1)
    if not veza_api_key:
        print("\nError: VEZA_API_KEY is required")
        sys.exit(1)

    print(f"Veza URL: {veza_url}")
    print(f"IdP Type: {args.idp_type}")
    if provider_prefix:
        print(f"Provider Prefix Filter: {provider_prefix}")

    # Initialize validator
    validator = DeploymentValidator(
        veza_url=veza_url,
        veza_api_key=veza_api_key,
        output_dir=output_dir
    )
    validator.debug = args.debug

    # Run validation
    if args.revalidate:
        results = validator.revalidate_if_failed(
            idp_type=args.idp_type,
            provider_prefix=provider_prefix
        )
    else:
        results = validator.validate(
            idp_type=args.idp_type,
            provider_prefix=provider_prefix,
            print_output=True
        )

    # Save results if requested
    if args.save:
        filepath = validator.save_results(results)
        print(f"\nResults saved to: {filepath}")

    # Exit with appropriate code
    if results.get("validation_passed"):
        print("\nValidation completed successfully.")
        sys.exit(0)
    elif results.get("revalidation_skipped"):
        print("\nNo re-validation needed (previous validation passed).")
        sys.exit(0)
    else:
        print("\nValidation completed with issues - see recommendations above.")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
================================================================================
CONFIGURATION VALIDATOR - Validate OAA Configuration
================================================================================

PURPOSE:
    Validates that OAA configurations in config/ are correctly formatted.
    Only shows OAA-specific targets (roles, permissions, settings).

USAGE:
    python -m config.validation.config_validator           # Run validations
    python -m config.validation.config_validator --verbose # Show details

================================================================================
"""

import sys
import argparse
from typing import List, Tuple


class ConfigValidator:
    """Configuration validator for ODIE-OAA config files."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def validate_role_definitions(self) -> Tuple[bool, List[str], dict]:
        """Validate ROLE_DEFINITIONS format and uniqueness."""
        errors = []
        stats = {"count": 0, "roles": []}

        try:
            from config.roles import ROLE_DEFINITIONS
        except ImportError as e:
            return False, [f"Cannot import ROLE_DEFINITIONS: {e}"], stats

        valid_permissions = {"C", "R", "U", "D", "M", "N", "?"}
        seen_names = set()
        seen_ids = set()

        for idx, entry in enumerate(ROLE_DEFINITIONS):
            if not isinstance(entry, tuple) or len(entry) != 3:
                errors.append(f"Entry {idx}: Must be tuple of (name, permissions, role_id)")
                continue

            name, permissions, role_id = entry

            if not isinstance(name, str):
                errors.append(f"Entry {idx}: Role name must be string")
            if not isinstance(permissions, list):
                errors.append(f"Entry {idx} ({name}): Permissions must be list")
            if not isinstance(role_id, str):
                errors.append(f"Entry {idx} ({name}): Role ID must be string")

            if name.lower() in seen_names:
                errors.append(f"Duplicate role name '{name}'")
            seen_names.add(name.lower())

            if role_id in seen_ids:
                errors.append(f"Duplicate role ID '{role_id}'")
            seen_ids.add(role_id)

            if isinstance(permissions, list):
                for perm in permissions:
                    if perm not in valid_permissions:
                        errors.append(f"Role '{name}': Invalid permission '{perm}'")

            stats["roles"].append({"name": name, "permissions": permissions})

        stats["count"] = len(ROLE_DEFINITIONS)
        return len(errors) == 0, errors, stats

    def validate_permission_mappings(self) -> Tuple[bool, List[str], dict]:
        """Validate PERMISSION_TO_ROLE and KNOWN_PERMISSIONS."""
        errors = []
        stats = {"mappings": 0, "known": 0}

        try:
            from config.roles import ROLE_DEFINITIONS, PERMISSION_TO_ROLE
            from config.settings import KNOWN_PERMISSIONS
        except ImportError as e:
            return False, [f"Cannot import: {e}"], stats

        valid_role_ids = {entry[2] for entry in ROLE_DEFINITIONS}

        for perm_name, role_id in PERMISSION_TO_ROLE.items():
            if perm_name != perm_name.lower():
                errors.append(f"Permission '{perm_name}' should be lowercase")
            if role_id not in valid_role_ids:
                errors.append(f"'{perm_name}' maps to unknown role '{role_id}'")

        for perm in KNOWN_PERMISSIONS:
            if perm != perm.lower():
                errors.append(f"Known permission '{perm}' should be lowercase")

        stats["mappings"] = len(PERMISSION_TO_ROLE)
        stats["known"] = len(KNOWN_PERMISSIONS)
        return len(errors) == 0, errors, stats

    def validate_base_permissions(self) -> Tuple[bool, List[str], dict]:
        """Validate BASE_PERMISSIONS format."""
        errors = []
        stats = {"count": 0, "symbols": []}

        try:
            from config.permissions import BASE_PERMISSIONS
            from oaaclient.templates import OAAPermission
        except ImportError as e:
            return False, [f"Cannot import: {e}"], stats

        seen_symbols = set()

        for idx, entry in enumerate(BASE_PERMISSIONS):
            if not isinstance(entry, tuple) or len(entry) != 3:
                errors.append(f"Entry {idx}: Must be tuple of (symbol, oaa_perms, description)")
                continue

            symbol, oaa_perms, description = entry

            if symbol in seen_symbols:
                errors.append(f"Duplicate symbol '{symbol}'")
            seen_symbols.add(symbol)

            if isinstance(oaa_perms, list):
                for oaa_perm in oaa_perms:
                    if not isinstance(oaa_perm, OAAPermission):
                        errors.append(f"Symbol '{symbol}': Invalid OAAPermission")

        stats["count"] = len(BASE_PERMISSIONS)
        stats["symbols"] = list(seen_symbols)
        return len(errors) == 0, errors, stats

    def run_all(self) -> bool:
        """Run all validation checks - OAA targets only."""
        print("\n" + "="*60)
        print("  ODIE-OAA CONFIGURATION VALIDATOR")
        print("="*60)

        all_passed = True

        # Roles
        print("\n  ROLES (config/roles.py)")
        print("  " + "-"*56)
        passed, errors, stats = self.validate_role_definitions()
        all_passed = all_passed and passed

        if passed:
            print(f"  [OK] {stats['count']} roles defined")
            if self.verbose:
                for role in stats["roles"]:
                    perms = ",".join(role["permissions"])
                    print(f"       - {role['name']}: [{perms}]")
        else:
            print(f"  [FAIL] Role validation failed")
            for err in errors:
                print(f"       - {err}")

        # Permission Mappings
        print("\n  PERMISSION MAPPINGS (config/roles.py, config/settings.py)")
        print("  " + "-"*56)
        passed, errors, stats = self.validate_permission_mappings()
        all_passed = all_passed and passed

        if passed:
            print(f"  [OK] {stats['mappings']} permission mappings, {stats['known']} known permissions")
        else:
            print(f"  [FAIL] Permission mapping validation failed")
            for err in errors:
                print(f"       - {err}")

        # Base Permissions
        print("\n  BASE PERMISSIONS (config/permissions.py)")
        print("  " + "-"*56)
        passed, errors, stats = self.validate_base_permissions()
        all_passed = all_passed and passed

        if passed:
            symbols = ", ".join(sorted(stats["symbols"]))
            print(f"  [OK] {stats['count']} base permissions: {symbols}")
        else:
            print(f"  [FAIL] Base permission validation failed")
            for err in errors:
                print(f"       - {err}")

        # Summary
        print("\n" + "="*60)
        if all_passed:
            print("  RESULT: ALL OAA CONFIGURATIONS VALID")
        else:
            print("  RESULT: CONFIGURATION ERRORS FOUND - Fix above issues")
        print("="*60 + "\n")

        return all_passed


def run_all_validations(verbose: bool = False) -> bool:
    """Run all validation checks (convenience function)."""
    validator = ConfigValidator(verbose=verbose)
    return validator.run_all()


def main():
    parser = argparse.ArgumentParser(description="Validate ODIE-OAA configuration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show role details")
    args = parser.parse_args()
    success = run_all_validations(verbose=args.verbose)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

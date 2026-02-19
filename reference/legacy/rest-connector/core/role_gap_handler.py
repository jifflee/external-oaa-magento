"""
Role Gap Handler - Workaround strategies for REST user-role gap.

The REST API does NOT return which role is assigned to which user.
GET /V1/customers/{id} lacks a role_id field.

This module provides 4 configurable strategies to handle this gap.
"""

import csv
import os
from typing import Dict, List, Any, Optional


class RoleGapHandler:
    """Handles the REST user-role assignment gap."""

    STRATEGIES = {"default_role", "csv_supplement", "all_roles", "skip"}

    def __init__(self, strategy: str = "default_role", csv_path: str = "", debug: bool = False):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"Invalid strategy: {strategy}. Must be one of: {self.STRATEGIES}")

        self.strategy = strategy
        self.csv_path = csv_path
        self.debug = debug

        # Print warning about the gap
        print(f"\n  REST API User-Role Gap:")
        print(f"  Strategy: {strategy}")
        if strategy == "default_role":
            print(f"  Non-admin users will be assigned 'Default User' role")
        elif strategy == "csv_supplement":
            print(f"  Loading user-role mapping from: {csv_path}")
        elif strategy == "all_roles":
            print(f"  Roles created but NO user-role links (cannot determine assignments)")
        elif strategy == "skip":
            print(f"  User-role relationships skipped entirely")

    def resolve(
        self,
        users: List[Dict],
        roles: List[Dict],
        company_id: str,
    ) -> List[Dict]:
        """Resolve user-role assignments using configured strategy.

        Args:
            users: List of user entities
            roles: List of role entities
            company_id: Company ID for role unique_id construction

        Returns:
            Updated users list with role_id populated where possible
        """
        if self.strategy == "default_role":
            return self._resolve_default_role(users, roles, company_id)
        elif self.strategy == "csv_supplement":
            return self._resolve_csv_supplement(users, roles, company_id)
        elif self.strategy == "all_roles":
            return self._resolve_all_roles(users)
        elif self.strategy == "skip":
            return self._resolve_skip(users)
        return users

    def _resolve_default_role(
        self, users: List[Dict], roles: List[Dict], company_id: str
    ) -> List[Dict]:
        """Assign 'Default User' role to non-admin users.

        Admin gets synthetic admin role. Other users get the first role
        named 'Default User' (case-insensitive), or the first role if
        no 'Default User' exists.
        """
        # Find default role
        default_role = None
        for role in roles:
            if role.get("name", "").lower() == "default user":
                default_role = role
                break

        if not default_role and roles:
            default_role = roles[0]  # Fallback to first role

        for user in users:
            if user.get("role_id"):
                continue  # Already assigned

            if user.get("is_company_admin"):
                # Admin gets all permissions implicitly
                # Find or create admin role
                admin_role = None
                for role in roles:
                    if "admin" in role.get("name", "").lower():
                        admin_role = role
                        break
                if admin_role:
                    user["role_id"] = admin_role["id"]
                    user["role_name"] = admin_role["name"]
            elif default_role:
                user["role_id"] = default_role["id"]
                user["role_name"] = default_role["name"]

        return users

    def _resolve_csv_supplement(
        self, users: List[Dict], roles: List[Dict], company_id: str
    ) -> List[Dict]:
        """Load user-role mapping from CSV file.

        CSV format: email,role_name
        """
        if not self.csv_path or not os.path.exists(self.csv_path):
            print(f"  WARNING: CSV file not found: {self.csv_path}")
            print(f"  Falling back to default_role strategy")
            return self._resolve_default_role(users, roles, company_id)

        # Load CSV mapping
        email_to_role = {}
        try:
            with open(self.csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get("email", "").strip().lower()
                    role_name = row.get("role_name", "").strip()
                    if email and role_name:
                        email_to_role[email] = role_name
        except Exception as e:
            print(f"  WARNING: Could not read CSV: {e}")
            return self._resolve_default_role(users, roles, company_id)

        if self.debug:
            print(f"  Loaded {len(email_to_role)} email-role mappings from CSV")

        # Build role name -> role dict
        role_by_name = {}
        for role in roles:
            role_by_name[role.get("name", "").lower()] = role

        # Apply mappings
        for user in users:
            if user.get("role_id"):
                continue

            csv_role_name = email_to_role.get(user["email"].lower())
            if csv_role_name:
                role = role_by_name.get(csv_role_name.lower())
                if role:
                    user["role_id"] = role["id"]
                    user["role_name"] = role["name"]
                elif self.debug:
                    print(f"  WARNING: Role '{csv_role_name}' from CSV not found for {user['email']}")

        return users

    def _resolve_all_roles(self, users: List[Dict]) -> List[Dict]:
        """Create roles but don't assign to users."""
        # Leave all role_id as None - roles exist but no links
        return users

    def _resolve_skip(self, users: List[Dict]) -> List[Dict]:
        """Skip user-role entirely."""
        for user in users:
            user["role_id"] = None
            user["role_name"] = None
        return users

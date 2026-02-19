"""Tests for core.role_gap_handler.RoleGapHandler (Commerce Cloud REST).

The RoleGapHandler is identical to the magento-rest on-prem version;
these tests verify that all four strategies behave correctly when imported
from the commerce-cloud-rest connector's core package.

Strategies tested:
  - default_role  : non-admin users receive 'Default User' role
  - all_roles     : roles are registered but no user-role links are created
  - skip          : role_id is explicitly set to None for all users
  - csv_supplement: role mapping loaded from a CSV file
"""

import os
import tempfile
import pytest

from core.role_gap_handler import RoleGapHandler


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def roles():
    return [
        {"id": "1", "name": "Company Administrator", "company_id": "2"},
        {"id": "2", "name": "Default User", "company_id": "2"},
        {"id": "3", "name": "Purchaser", "company_id": "2"},
    ]


@pytest.fixture
def users():
    return [
        {
            "email": "admin@acme.com",
            "is_company_admin": True,
            "role_id": None,
            "role_name": None,
        },
        {
            "email": "jane@acme.com",
            "is_company_admin": False,
            "role_id": None,
            "role_name": None,
        },
        {
            "email": "bob@acme.com",
            "is_company_admin": False,
            "role_id": None,
            "role_name": None,
        },
    ]


# ---------------------------------------------------------------------------
# Strategy: default_role
# ---------------------------------------------------------------------------

class TestDefaultRoleStrategy:
    def test_non_admin_gets_default_user_role(self, users, roles):
        handler = RoleGapHandler(strategy="default_role")
        result = handler.resolve(users, roles, company_id="2")
        jane = next(u for u in result if u["email"] == "jane@acme.com")
        assert jane["role_id"] == "2"
        assert jane["role_name"] == "Default User"

    def test_admin_gets_admin_role(self, users, roles):
        handler = RoleGapHandler(strategy="default_role")
        result = handler.resolve(users, roles, company_id="2")
        admin = next(u for u in result if u["email"] == "admin@acme.com")
        assert admin["role_id"] == "1"
        assert "admin" in admin["role_name"].lower()

    def test_all_users_get_role_assigned(self, users, roles):
        handler = RoleGapHandler(strategy="default_role")
        result = handler.resolve(users, roles, company_id="2")
        for user in result:
            assert user["role_id"] is not None

    def test_already_assigned_role_not_overwritten(self, roles):
        users_with_role = [
            {"email": "pre@acme.com", "is_company_admin": False, "role_id": "3", "role_name": "Purchaser"},
        ]
        handler = RoleGapHandler(strategy="default_role")
        result = handler.resolve(users_with_role, roles, company_id="2")
        assert result[0]["role_id"] == "3"

    def test_fallback_to_first_role_when_no_default_user_role(self, users):
        roles_no_default = [
            {"id": "1", "name": "Admin", "company_id": "2"},
            {"id": "2", "name": "Custom Role", "company_id": "2"},
        ]
        handler = RoleGapHandler(strategy="default_role")
        result = handler.resolve(users, roles_no_default, company_id="2")
        jane = next(u for u in result if u["email"] == "jane@acme.com")
        # Fallback: first role in list
        assert jane["role_id"] == "1"


# ---------------------------------------------------------------------------
# Strategy: all_roles
# ---------------------------------------------------------------------------

class TestAllRolesStrategy:
    def test_users_keep_no_role_id(self, users, roles):
        handler = RoleGapHandler(strategy="all_roles")
        result = handler.resolve(users, roles, company_id="2")
        for user in result:
            assert user["role_id"] is None


# ---------------------------------------------------------------------------
# Strategy: skip
# ---------------------------------------------------------------------------

class TestSkipStrategy:
    def test_all_role_ids_set_to_none(self, users, roles):
        # Pre-assign a role to verify skip clears it
        users[0]["role_id"] = "1"
        handler = RoleGapHandler(strategy="skip")
        result = handler.resolve(users, roles, company_id="2")
        for user in result:
            assert user["role_id"] is None
            assert user["role_name"] is None


# ---------------------------------------------------------------------------
# Strategy: csv_supplement
# ---------------------------------------------------------------------------

class TestCsvSupplementStrategy:
    def test_loads_mapping_from_csv(self, users, roles):
        csv_content = "email,role_name\njane@acme.com,Purchaser\nbob@acme.com,Default User\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            csv_path = f.name
        try:
            handler = RoleGapHandler(strategy="csv_supplement", csv_path=csv_path)
            result = handler.resolve(users, roles, company_id="2")
            jane = next(u for u in result if u["email"] == "jane@acme.com")
            assert jane["role_id"] == "3"
            assert jane["role_name"] == "Purchaser"
        finally:
            os.unlink(csv_path)

    def test_falls_back_to_default_role_when_csv_missing(self, users, roles):
        handler = RoleGapHandler(strategy="csv_supplement", csv_path="/nonexistent/mapping.csv")
        result = handler.resolve(users, roles, company_id="2")
        # Should fall back to default_role strategy
        for user in result:
            assert user["role_id"] is not None


# ---------------------------------------------------------------------------
# Invalid strategy
# ---------------------------------------------------------------------------

class TestInvalidStrategy:
    def test_raises_on_unknown_strategy(self):
        with pytest.raises(ValueError, match="Invalid strategy"):
            RoleGapHandler(strategy="unknown_strategy")

"""
Tests for core.role_gap_handler.RoleGapHandler.

Uses in-memory sample data; CSV tests use pytest's tmp_path fixture.
"""

import csv
import os
import pytest

from core.role_gap_handler import RoleGapHandler


# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------


def sample_users():
    return [
        {"email": "admin@acme.com", "is_company_admin": True, "role_id": None, "role_name": None},
        {"email": "user1@acme.com", "is_company_admin": False, "role_id": None, "role_name": None},
        {"email": "user2@acme.com", "is_company_admin": False, "role_id": None, "role_name": None},
    ]


def sample_roles():
    return [
        {"id": "1", "name": "Company Administrator", "company_id": "2"},
        {"id": "2", "name": "Default User", "company_id": "2"},
        {"id": "3", "name": "Purchaser", "company_id": "2"},
    ]


COMPANY_ID = "2"


# ---------------------------------------------------------------------------
# Strategy: default_role
# ---------------------------------------------------------------------------


class TestDefaultRoleStrategy:
    def test_default_role_assigns_non_admin(self):
        handler = RoleGapHandler(strategy="default_role")
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        non_admins = [u for u in result if not u["is_company_admin"]]
        for user in non_admins:
            assert user["role_id"] == "2", f"Expected 'Default User' (id=2) for {user['email']}"
            assert user["role_name"] == "Default User"

    def test_default_role_assigns_admin_role(self):
        handler = RoleGapHandler(strategy="default_role")
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        admin = next(u for u in result if u["is_company_admin"])
        # Admin role is the one whose name contains "admin" (case-insensitive)
        assert admin["role_id"] == "1"
        assert admin["role_name"] == "Company Administrator"

    def test_all_users_get_role_assigned(self):
        handler = RoleGapHandler(strategy="default_role")
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        for user in result:
            assert user["role_id"] is not None, f"{user['email']} should have a role"

    def test_fallback_to_first_role_when_no_default_user_role(self):
        """When no role is named 'Default User', fallback to roles[0]."""
        handler = RoleGapHandler(strategy="default_role")
        custom_roles = [
            {"id": "10", "name": "Buyer", "company_id": "2"},
            {"id": "11", "name": "Viewer", "company_id": "2"},
        ]
        users = [
            {"email": "user@acme.com", "is_company_admin": False, "role_id": None, "role_name": None}
        ]
        result = handler.resolve(users, custom_roles, COMPANY_ID)
        # Fallback: first role
        assert result[0]["role_id"] == "10"

    def test_no_roles_available_leaves_role_id_none(self):
        """If the roles list is empty, role_id cannot be assigned."""
        handler = RoleGapHandler(strategy="default_role")
        users = [
            {"email": "user@acme.com", "is_company_admin": False, "role_id": None, "role_name": None}
        ]
        result = handler.resolve(users, [], COMPANY_ID)
        assert result[0]["role_id"] is None


# ---------------------------------------------------------------------------
# Strategy: csv_supplement
# ---------------------------------------------------------------------------


class TestCsvSupplementStrategy:
    def test_csv_supplement_loads_mapping(self, tmp_path):
        """CSV file populates user roles from email->role_name mapping."""
        csv_file = tmp_path / "role_mapping.csv"
        csv_file.write_text("email,role_name\nuser1@acme.com,Purchaser\nuser2@acme.com,Default User\n")

        handler = RoleGapHandler(strategy="csv_supplement", csv_path=str(csv_file))
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        user1 = next(u for u in result if u["email"] == "user1@acme.com")
        assert user1["role_id"] == "3"
        assert user1["role_name"] == "Purchaser"

        user2 = next(u for u in result if u["email"] == "user2@acme.com")
        assert user2["role_id"] == "2"
        assert user2["role_name"] == "Default User"

    def test_csv_supplement_fallback_on_missing_file(self):
        """Falls back to default_role when the CSV path does not exist."""
        handler = RoleGapHandler(
            strategy="csv_supplement",
            csv_path="/nonexistent/path/mapping.csv",
        )
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        # Fallback behaves like default_role: non-admins get Default User
        non_admins = [u for u in result if not u["is_company_admin"]]
        for user in non_admins:
            assert user["role_id"] == "2"

    def test_csv_supplement_email_case_insensitive(self, tmp_path):
        """Emails in CSV are matched case-insensitively."""
        csv_file = tmp_path / "mapping.csv"
        csv_file.write_text("email,role_name\nUSER1@ACME.COM,Purchaser\n")

        handler = RoleGapHandler(strategy="csv_supplement", csv_path=str(csv_file))
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        user1 = next(u for u in result if u["email"] == "user1@acme.com")
        assert user1["role_id"] == "3"

    def test_csv_supplement_unknown_role_name_leaves_none(self, tmp_path):
        """If a role name from CSV doesn't match any role, role_id stays None."""
        csv_file = tmp_path / "mapping.csv"
        csv_file.write_text("email,role_name\nuser1@acme.com,NonExistentRole\n")

        handler = RoleGapHandler(strategy="csv_supplement", csv_path=str(csv_file), debug=True)
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        user1 = next(u for u in result if u["email"] == "user1@acme.com")
        assert user1["role_id"] is None

    def test_csv_supplement_skips_empty_rows(self, tmp_path):
        """Rows with missing email or role_name are ignored."""
        csv_file = tmp_path / "mapping.csv"
        csv_file.write_text("email,role_name\n,Default User\nuser1@acme.com,\n")

        handler = RoleGapHandler(strategy="csv_supplement", csv_path=str(csv_file))
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        user1 = next(u for u in result if u["email"] == "user1@acme.com")
        # No valid mapping was loaded, so role_id stays None
        assert user1["role_id"] is None

    def test_csv_with_bom_encoding(self, tmp_path):
        """CSV files with UTF-8 BOM (common from Excel) should be handled."""
        csv_file = tmp_path / "mapping_bom.csv"
        # Write with BOM
        with open(str(csv_file), "w", encoding="utf-8-sig") as fh:
            fh.write("email,role_name\nuser1@acme.com,Purchaser\n")

        handler = RoleGapHandler(strategy="csv_supplement", csv_path=str(csv_file))
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        user1 = next(u for u in result if u["email"] == "user1@acme.com")
        assert user1["role_id"] == "3"


# ---------------------------------------------------------------------------
# Strategy: all_roles
# ---------------------------------------------------------------------------


class TestAllRolesStrategy:
    def test_all_roles_no_assignment(self):
        """all_roles creates roles but assigns none to users."""
        handler = RoleGapHandler(strategy="all_roles")
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        for user in result:
            assert user["role_id"] is None, f"{user['email']} should have no role assignment"

    def test_all_roles_does_not_mutate_role_name(self):
        handler = RoleGapHandler(strategy="all_roles")
        users = sample_users()
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        for user in result:
            assert user["role_name"] is None


# ---------------------------------------------------------------------------
# Strategy: skip
# ---------------------------------------------------------------------------


class TestSkipStrategy:
    def test_skip_clears_assignments(self):
        """skip strategy explicitly sets role_id=None for all users."""
        users = sample_users()
        # Pre-set one user to have a role to verify skip clears it
        users[0]["role_id"] = "1"
        users[0]["role_name"] = "Company Administrator"

        handler = RoleGapHandler(strategy="skip")
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        for user in result:
            assert user["role_id"] is None
            assert user["role_name"] is None

    def test_skip_clears_for_all_users_regardless_of_state(self):
        handler = RoleGapHandler(strategy="skip")
        users = [
            {"email": "a@x.com", "is_company_admin": True, "role_id": "1", "role_name": "Admin"},
            {"email": "b@x.com", "is_company_admin": False, "role_id": None, "role_name": None},
        ]
        result = handler.resolve(users, sample_roles(), COMPANY_ID)
        for user in result:
            assert user["role_id"] is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestInvalidStrategy:
    def test_invalid_strategy_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid strategy"):
            RoleGapHandler(strategy="bogus_strategy")

    def test_valid_strategies_do_not_raise(self):
        for strategy in ("default_role", "csv_supplement", "all_roles", "skip"):
            # Should not raise
            RoleGapHandler(strategy=strategy)


# ---------------------------------------------------------------------------
# Pre-existing role_id not overwritten
# ---------------------------------------------------------------------------


class TestExistingRoleNotOverwritten:
    def test_existing_role_id_preserved_in_default_role(self):
        """Users that already have role_id set must not be changed."""
        handler = RoleGapHandler(strategy="default_role")
        users = [
            {
                "email": "user1@acme.com",
                "is_company_admin": False,
                "role_id": "3",  # pre-assigned Purchaser
                "role_name": "Purchaser",
            },
            {
                "email": "user2@acme.com",
                "is_company_admin": False,
                "role_id": None,
                "role_name": None,
            },
        ]
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        user1 = next(u for u in result if u["email"] == "user1@acme.com")
        assert user1["role_id"] == "3"  # untouched
        assert user1["role_name"] == "Purchaser"

    def test_existing_role_id_preserved_in_csv_supplement(self, tmp_path):
        """CSV should not overwrite a user that already has a role_id."""
        csv_file = tmp_path / "mapping.csv"
        csv_file.write_text("email,role_name\nuser1@acme.com,Default User\n")

        handler = RoleGapHandler(strategy="csv_supplement", csv_path=str(csv_file))
        users = [
            {
                "email": "user1@acme.com",
                "is_company_admin": False,
                "role_id": "3",  # pre-assigned
                "role_name": "Purchaser",
            }
        ]
        result = handler.resolve(users, sample_roles(), COMPANY_ID)

        user1 = result[0]
        assert user1["role_id"] == "3"  # not overwritten by CSV

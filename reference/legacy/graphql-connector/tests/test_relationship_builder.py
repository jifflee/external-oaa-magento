"""
Tests for core.relationship_builder.

RelationshipBuilder depends on oaaclient, which may not be installed in all
environments.  Every test is skipped gracefully when oaaclient is unavailable.

Strategy
--------
We build a real ApplicationBuilder output (CustomApplication) from sample
entities and then call RelationshipBuilder.build_all() against it, asserting
on the resulting graph state.

Where oaaclient internal API surfaces are not stable we assert on observable
side-effects (group membership collections, role assignments, etc.) rather
than private attributes.
"""

import json
import os

import pytest

# Skip entire module if oaaclient is not installed
oaaclient = pytest.importorskip("oaaclient", reason="oaaclient not installed")

from core.application_builder import ApplicationBuilder          # noqa: E402
from core.relationship_builder import RelationshipBuilder        # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_rest_roles():
    path = os.path.join(FIXTURES_DIR, "rest_roles_response.json")
    with open(path) as f:
        return json.load(f)["items"]


def sample_entities():
    return {
        "company": {
            "id": "1",
            "name": "Acme Corp",
            "legal_name": "Acme Corporation LLC",
            "email": "info@acme.com",
            "admin_email": "admin@acme.com",
            "admin_firstname": "John",
            "admin_lastname": "Admin",
            "graphql_id": "MQ==",
        },
        "users": [
            {
                "email": "admin@acme.com",
                "firstname": "John",
                "lastname": "Admin",
                "job_title": "CEO",
                "telephone": "555-0001",
                "is_active": True,
                "status_raw": "ACTIVE",
                "is_company_admin": True,
                "company_id": "1",
                "team_id": None,
                "role_id": "1",
                "role_name": "Company Administrator",
            },
            {
                "email": "jane@acme.com",
                "firstname": "Jane",
                "lastname": "Developer",
                "job_title": "Senior Developer",
                "telephone": "555-0002",
                "is_active": True,
                "status_raw": "ACTIVE",
                "is_company_admin": False,
                "company_id": "1",
                "team_id": "1",
                "role_id": "2",
                "role_name": "Default User",
            },
            {
                "email": "bob@acme.com",
                "firstname": "Bob",
                "lastname": "Buyer",
                "job_title": "Procurement",
                "telephone": "555-0003",
                "is_active": False,
                "status_raw": "INACTIVE",
                "is_company_admin": False,
                "company_id": "1",
                "team_id": None,
                "role_id": "3",
                "role_name": "Purchaser",
            },
        ],
        "teams": [
            {
                "id": "1",
                "name": "Engineering",
                "description": "Engineering team",
                "company_id": "1",
                "graphql_id": "MQ==",
            }
        ],
        "roles": [
            {"id": "1", "name": "Company Administrator", "company_id": "1", "graphql_id": "MQ=="},
            {"id": "2", "name": "Default User", "company_id": "1", "graphql_id": "Mg=="},
            {"id": "3", "name": "Purchaser", "company_id": "1", "graphql_id": "Mw=="},
        ],
        "hierarchy": [
            # jane (Customer) child of Engineering team (CompanyTeam)
            {
                "child_type": "CompanyTeam",
                "child_entity": {"id": "1", "name": "Engineering", "company_id": "1"},
                "parent_type": "Customer",
                "parent_entity": {"email": "admin@acme.com"},
            },
            {
                "child_type": "Customer",
                "child_entity": {"email": "jane@acme.com"},
                "parent_type": "CompanyTeam",
                "parent_entity": {"id": "1", "name": "Engineering"},
            },
            # bob (Customer) reports to admin (Customer)
            {
                "child_type": "Customer",
                "child_entity": {"email": "bob@acme.com"},
                "parent_type": "Customer",
                "parent_entity": {"email": "admin@acme.com"},
            },
        ],
        "admin_email": "admin@acme.com",
    }


def build_app_and_run_relationships(entities=None, rest_roles=None):
    """Helper: build the CustomApplication, then apply all relationships."""
    if entities is None:
        entities = sample_entities()
    app = ApplicationBuilder(store_url="https://store.example.com", debug=False).build(entities)
    RelationshipBuilder(debug=False).build_all(app, entities, rest_roles)
    return app


# ---------------------------------------------------------------------------
# User -> Company membership
# ---------------------------------------------------------------------------


def test_build_user_company_membership():
    """All users are added to the company group after build_all()."""
    app = build_app_and_run_relationships()

    for email in ("admin@acme.com", "jane@acme.com", "bob@acme.com"):
        user = app.local_users[email]
        # groups is a set/list of group unique_ids the user belongs to
        assert "company_1" in user.groups, (
            f"Expected {email} to be a member of company_1"
        )


# ---------------------------------------------------------------------------
# User -> Team membership
# ---------------------------------------------------------------------------


def test_build_user_team_membership():
    """Jane (team_id='1') is added to the team_1 group; others are not."""
    app = build_app_and_run_relationships()

    jane = app.local_users["jane@acme.com"]
    assert "team_1" in jane.groups

    admin = app.local_users["admin@acme.com"]
    assert "team_1" not in admin.groups

    bob = app.local_users["bob@acme.com"]
    assert "team_1" not in bob.groups


# ---------------------------------------------------------------------------
# User -> Role assignment
# ---------------------------------------------------------------------------


def test_build_user_role_assignment():
    """Each user is assigned the correct role unique_id."""
    app = build_app_and_run_relationships()

    admin = app.local_users["admin@acme.com"]
    assert "role_1_1" in admin.roles

    jane = app.local_users["jane@acme.com"]
    assert "role_1_2" in jane.roles

    bob = app.local_users["bob@acme.com"]
    assert "role_1_3" in bob.roles


# ---------------------------------------------------------------------------
# Role -> Permission (with REST supplement)
# ---------------------------------------------------------------------------


def test_build_role_permissions_from_rest():
    """With REST supplement, roles gain permission links for 'allow' entries."""
    rest_roles = load_rest_roles()
    app = build_app_and_run_relationships(rest_roles=rest_roles)

    # Company Administrator role should have at least 1 permission linked
    admin_role = app.local_roles["role_1_1"]
    assert len(admin_role.permissions) >= 1

    # Verify a specific expected permission is present
    permission_ids = set(admin_role.permissions)
    assert "Magento_Company::index" in permission_ids


def test_build_role_permissions_no_rest():
    """Without REST supplement, roles have no permission links (cannot infer from GraphQL)."""
    app = build_app_and_run_relationships(rest_roles=None)

    for role_uid in ("role_1_1", "role_1_2", "role_1_3"):
        role = app.local_roles[role_uid]
        assert len(role.permissions) == 0, (
            f"Expected no permissions on {role_uid} without REST supplement"
        )


# ---------------------------------------------------------------------------
# Team -> Company parent group
# ---------------------------------------------------------------------------


def test_build_team_company_parent():
    """The Engineering team is added as a sub-group of the company group."""
    app = build_app_and_run_relationships()

    company_group = app.local_groups["company_1"]
    # OAA groups track nested groups in a 'groups' attribute (set of unique_ids)
    assert "team_1" in company_group.groups


# ---------------------------------------------------------------------------
# User -> User reports_to
# ---------------------------------------------------------------------------


def test_build_reports_to():
    """Bob (Customer -> Customer hierarchy) gets reports_to pointing to admin email."""
    app = build_app_and_run_relationships()

    bob = app.local_users["bob@acme.com"]
    # reports_to is stored as a custom property on the user
    assert bob.properties.get("reports_to") == "admin@acme.com"


def test_reports_to_not_set_for_non_customer_parent():
    """Jane's parent is a CompanyTeam, so no reports_to property is set."""
    app = build_app_and_run_relationships()

    jane = app.local_users["jane@acme.com"]
    # reports_to should be absent or None when parent is not a Customer
    assert jane.properties.get("reports_to") is None


# ---------------------------------------------------------------------------
# Deny permissions are excluded
# ---------------------------------------------------------------------------


def test_deny_permissions_excluded():
    """Permissions with 'deny' value do not create role->permission links."""
    rest_roles = load_rest_roles()
    app = build_app_and_run_relationships(rest_roles=rest_roles)

    # Default User (role_1_2) has "Magento_NegotiableQuote::all" as 'deny'
    default_user_role = app.local_roles["role_1_2"]
    assert "Magento_NegotiableQuote::all" not in default_user_role.permissions

    # Default User also has "Magento_Company::user_management" as 'deny'
    assert "Magento_Company::user_management" not in default_user_role.permissions

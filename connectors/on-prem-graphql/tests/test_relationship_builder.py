"""Tests for core.relationship_builder."""

import json
import os
import pytest

oaaclient = pytest.importorskip("oaaclient", reason="oaaclient not installed")

from core.application_builder import ApplicationBuilder  # noqa: E402
from core.relationship_builder import RelationshipBuilder  # noqa: E402

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
    if entities is None:
        entities = sample_entities()
    app = ApplicationBuilder(store_url="https://store.example.com", debug=False).build(entities)
    RelationshipBuilder(debug=False).build_all(app, entities, rest_roles)
    return app


def test_build_user_company_membership():
    app = build_app_and_run_relationships()
    for email in ("admin@acme.com", "jane@acme.com", "bob@acme.com"):
        user = app.local_users[email]
        assert "company_1" in user.groups, f"Expected {email} to be a member of company_1"


def test_build_user_team_membership():
    app = build_app_and_run_relationships()
    jane = app.local_users["jane@acme.com"]
    assert "team_1" in jane.groups
    admin = app.local_users["admin@acme.com"]
    assert "team_1" not in admin.groups
    bob = app.local_users["bob@acme.com"]
    assert "team_1" not in bob.groups


def test_build_user_role_assignment():
    app = build_app_and_run_relationships()
    admin = app.local_users["admin@acme.com"]
    assert "role_1_1" in admin.role_assignments
    jane = app.local_users["jane@acme.com"]
    assert "role_1_2" in jane.role_assignments
    bob = app.local_users["bob@acme.com"]
    assert "role_1_3" in bob.role_assignments


def test_build_role_permissions_from_rest():
    rest_roles = load_rest_roles()
    app = build_app_and_run_relationships(rest_roles=rest_roles)
    admin_role = app.local_roles["role_1_1"]
    assert len(admin_role.permissions) >= 1
    permission_ids = set(admin_role.permissions)
    assert "Magento_Company::index" in permission_ids


def test_build_role_permissions_no_rest():
    app = build_app_and_run_relationships(rest_roles=None)
    for role_uid in ("role_1_1", "role_1_2", "role_1_3"):
        role = app.local_roles[role_uid]
        assert len(role.permissions) == 0


def test_build_team_company_parent():
    app = build_app_and_run_relationships()
    company_group = app.local_groups["company_1"]
    assert "team_1" in company_group.groups


def test_build_reports_to():
    app = build_app_and_run_relationships()
    bob = app.local_users["bob@acme.com"]
    assert bob.properties.get("reports_to") == "admin@acme.com"


def test_reports_to_not_set_for_non_customer_parent():
    app = build_app_and_run_relationships()
    jane = app.local_users["jane@acme.com"]
    assert jane.properties.get("reports_to") is None


def test_deny_permissions_excluded():
    rest_roles = load_rest_roles()
    app = build_app_and_run_relationships(rest_roles=rest_roles)
    default_user_role = app.local_roles["role_1_2"]
    assert "Magento_NegotiableQuote::all" not in default_user_role.permissions
    assert "Magento_Company::user_management" not in default_user_role.permissions

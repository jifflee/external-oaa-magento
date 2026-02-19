"""Tests for core.application_builder."""

import pytest

oaaclient = pytest.importorskip("oaaclient", reason="oaaclient not installed")

from core.application_builder import ApplicationBuilder  # noqa: E402


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
        "hierarchy": [],
        "admin_email": "admin@acme.com",
    }


def build_app(entities=None, store_url="https://store.example.com"):
    if entities is None:
        entities = sample_entities()
    builder = ApplicationBuilder(store_url=store_url, debug=False)
    return builder.build(entities)


def test_build_creates_application():
    app = build_app()
    assert app.name == "magento_onprem_graphql_1"


def test_build_adds_users():
    app = build_app()
    assert len(app.local_users) == 3
    expected_emails = {"admin@acme.com", "jane@acme.com", "bob@acme.com"}
    assert set(app.local_users.keys()) == expected_emails


def test_build_adds_company_group():
    app = build_app()
    company_group = app.local_groups.get("company_1")
    assert company_group is not None
    assert company_group.group_type == "company"


def test_build_adds_team_groups():
    app = build_app()
    team_group = app.local_groups.get("team_1")
    assert team_group is not None
    assert team_group.group_type == "team"


def test_build_adds_roles():
    app = build_app()
    assert len(app.local_roles) == 3
    assert "role_1_1" in app.local_roles
    assert "role_1_2" in app.local_roles
    assert "role_1_3" in app.local_roles


def test_build_user_properties():
    app = build_app()
    admin_user = app.local_users["admin@acme.com"]
    assert admin_user.properties.get("is_company_admin") is True
    jane_user = app.local_users["jane@acme.com"]
    assert jane_user.properties.get("is_company_admin") is False
    assert jane_user.properties.get("company_id") == "1"


def test_build_user_identity():
    app = build_app()
    for email, local_user in app.local_users.items():
        assert email in local_user.identities


def test_build_inactive_user():
    app = build_app()
    bob = app.local_users["bob@acme.com"]
    assert bob.is_active is False


def test_build_active_user():
    app = build_app()
    admin = app.local_users["admin@acme.com"]
    assert admin.is_active is True


def test_build_user_firstname_lastname():
    app = build_app()
    jane = app.local_users["jane@acme.com"]
    assert jane.first_name == "Jane"
    assert jane.last_name == "Developer"


def test_build_role_unique_id_format():
    app = build_app()
    purchaser_role = app.local_roles.get("role_1_3")
    assert purchaser_role is not None
    assert purchaser_role.name == "Purchaser"

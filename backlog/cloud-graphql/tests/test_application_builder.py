"""Tests for core.application_builder (Commerce Cloud GraphQL).

Verifies that ApplicationBuilder produces an OAA CustomApplication
with Commerce Cloud GraphQL-specific naming conventions:
  - app_name_prefix: commerce_cloud_graphql
  - application_type: Magento B2B Commerce Cloud (GraphQL)
"""

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
        },
        "users": [
            {
                "email": "admin@acme.com",
                "firstname": "John",
                "lastname": "Admin",
                "job_title": "CEO",
                "telephone": "555-0001",
                "is_active": True,
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
                "is_company_admin": False,
                "company_id": "1",
                "team_id": "1",
                "role_id": "2",
                "role_name": "Default User",
            },
        ],
        "teams": [
            {"id": "1", "name": "Engineering", "description": "Eng team", "company_id": "1"}
        ],
        "roles": [
            {"id": "1", "name": "Company Administrator", "company_id": "1"},
            {"id": "2", "name": "Default User", "company_id": "1"},
        ],
        "hierarchy": [],
        "admin_email": "admin@acme.com",
    }


def build_app(entities=None):
    if entities is None:
        entities = sample_entities()
    return ApplicationBuilder(store_url="https://cloud.example.com", debug=False).build(entities)


def test_build_creates_application():
    app = build_app()
    assert app.name == "commerce_cloud_graphql_1"


def test_build_adds_users():
    app = build_app()
    assert len(app.local_users) == 2
    assert "admin@acme.com" in app.local_users
    assert "jane@acme.com" in app.local_users


def test_build_adds_company_group():
    app = build_app()
    assert "company_1" in app.local_groups


def test_build_adds_team_groups():
    app = build_app()
    assert "team_1" in app.local_groups


def test_build_adds_roles():
    app = build_app()
    assert len(app.local_roles) == 2
    assert "role_1_1" in app.local_roles
    assert "role_1_2" in app.local_roles


def test_build_user_properties():
    app = build_app()
    admin = app.local_users["admin@acme.com"]
    assert admin.properties.get("is_company_admin") is True


def test_build_user_identity():
    app = build_app()
    for email, user in app.local_users.items():
        assert email in user.identities

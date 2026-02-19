"""Tests for magento_oaa_shared.application_builder_base.BaseApplicationBuilder."""

import pytest

oaaclient = pytest.importorskip("oaaclient", reason="oaaclient not installed")

from magento_oaa_shared.application_builder_base import BaseApplicationBuilder  # noqa: E402


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
                "magento_customer_id": "10",
            },
            {
                "email": "jane@acme.com",
                "firstname": "Jane",
                "lastname": "Dev",
                "job_title": "",
                "telephone": "",
                "is_active": True,
                "is_company_admin": False,
                "company_id": "1",
            },
        ],
        "teams": [
            {"id": "1", "name": "Engineering", "description": "Eng team", "company_id": "1"},
        ],
        "roles": [
            {"id": "1", "name": "Admin Role", "company_id": "1"},
            {"id": "2", "name": "User Role", "company_id": "1"},
        ],
        "hierarchy": [],
        "admin_email": "admin@acme.com",
    }


def build(prefix="test_prefix", app_type="Test Type", **kwargs):
    builder = BaseApplicationBuilder(
        store_url="https://store.example.com",
        app_name_prefix=prefix,
        application_type=app_type,
        description_suffix="test connector",
        **kwargs,
    )
    return builder.build(sample_entities())


def test_app_name_uses_prefix():
    app = build(prefix="my_connector")
    assert app.name == "my_connector_1"


def test_app_type():
    app = build(app_type="My Custom Type")
    assert app.application_type == "My Custom Type"


def test_app_description_contains_company_name():
    app = build()
    assert "Acme Corp" in app.description


def test_users_added():
    app = build()
    assert len(app.local_users) == 2
    assert "admin@acme.com" in app.local_users
    assert "jane@acme.com" in app.local_users


def test_user_properties():
    app = build()
    admin = app.local_users["admin@acme.com"]
    assert admin.first_name == "John"
    assert admin.last_name == "Admin"
    assert admin.is_active is True
    assert admin.properties.get("is_company_admin") is True
    assert admin.properties.get("company_id") == "1"
    assert admin.properties.get("magento_customer_id") == "10"


def test_user_identity():
    app = build()
    for email, user in app.local_users.items():
        assert email in user.identities


def test_company_group():
    app = build()
    group = app.local_groups.get("company_1")
    assert group is not None
    assert group.group_type == "company"
    assert group.name == "Acme Corp"


def test_team_group():
    app = build()
    group = app.local_groups.get("team_1")
    assert group is not None
    assert group.group_type == "team"


def test_roles():
    app = build()
    assert len(app.local_roles) == 2
    assert "role_1_1" in app.local_roles
    assert "role_1_2" in app.local_roles


def test_permissions_defined():
    app = build()
    assert len(app.custom_permissions) == 34


def test_empty_job_title_not_set():
    app = build()
    jane = app.local_users["jane@acme.com"]
    assert not jane.properties.get("job_title")

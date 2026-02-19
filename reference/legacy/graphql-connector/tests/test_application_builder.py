"""
Tests for core.application_builder.

ApplicationBuilder depends on oaaclient, which may not be installed in all
environments.  Every test is therefore skipped gracefully when oaaclient is
unavailable using pytest.importorskip.

Fixture data is provided by the sample_entities() helper so that no live
GraphQL call is needed.
"""

import pytest

# Skip the entire module if oaaclient is not installed
oaaclient = pytest.importorskip("oaaclient", reason="oaaclient not installed")

from core.application_builder import ApplicationBuilder  # noqa: E402 (import after skip guard)


# ---------------------------------------------------------------------------
# Synthetic entity fixture
# ---------------------------------------------------------------------------


def sample_entities():
    """Return a minimal entities dict that mirrors EntityExtractor output."""
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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def build_app(entities=None, store_url="https://store.example.com"):
    """Instantiate ApplicationBuilder and call build()."""
    if entities is None:
        entities = sample_entities()
    builder = ApplicationBuilder(store_url=store_url, debug=False)
    return builder.build(entities)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_build_creates_application():
    """Built application name follows 'magento_b2b_{company_id}' pattern."""
    app = build_app()
    assert app.name == "magento_b2b_graphql_1"


def test_build_adds_users():
    """All users are present as local_users; unique_id is the email address."""
    app = build_app()
    assert len(app.local_users) == 3

    expected_emails = {"admin@acme.com", "jane@acme.com", "bob@acme.com"}
    assert set(app.local_users.keys()) == expected_emails


def test_build_adds_company_group():
    """One local_group with unique_id 'company_1' and group_type 'company' is created."""
    app = build_app()

    company_group = app.local_groups.get("company_1")
    assert company_group is not None
    assert company_group.group_type == "company"


def test_build_adds_team_groups():
    """Engineering team is added as a local_group with group_type 'team'."""
    app = build_app()

    team_group = app.local_groups.get("team_1")
    assert team_group is not None
    assert team_group.group_type == "team"


def test_build_adds_roles():
    """Three roles are added; each unique_id follows 'role_{company_id}_{role_id}' format."""
    app = build_app()
    assert len(app.local_roles) == 3

    assert "role_1_1" in app.local_roles
    assert "role_1_2" in app.local_roles
    assert "role_1_3" in app.local_roles


def test_build_user_properties():
    """Custom properties (job_title, telephone, is_company_admin, company_id) are set."""
    app = build_app()

    admin_user = app.local_users["admin@acme.com"]
    # is_company_admin custom property
    assert admin_user.properties.get("is_company_admin") is True

    jane_user = app.local_users["jane@acme.com"]
    assert jane_user.properties.get("is_company_admin") is False
    assert jane_user.properties.get("company_id") == "1"


def test_build_user_identity():
    """Each user has an identity added that equals their email address."""
    app = build_app()

    for email, local_user in app.local_users.items():
        assert email in local_user.identities


def test_build_inactive_user():
    """Bob (INACTIVE) has is_active=False on the local_user object."""
    app = build_app()

    bob = app.local_users["bob@acme.com"]
    assert bob.is_active is False


def test_build_active_user():
    """John (ACTIVE) has is_active=True on the local_user object."""
    app = build_app()

    admin = app.local_users["admin@acme.com"]
    assert admin.is_active is True


def test_build_user_firstname_lastname():
    """first_name and last_name are mapped from user dict."""
    app = build_app()

    jane = app.local_users["jane@acme.com"]
    assert jane.first_name == "Jane"
    assert jane.last_name == "Developer"


def test_build_role_unique_id_format():
    """Role unique_id encodes both company_id and role_id to avoid collisions."""
    app = build_app()

    purchaser_role = app.local_roles.get("role_1_3")
    assert purchaser_role is not None
    assert purchaser_role.name == "Purchaser"

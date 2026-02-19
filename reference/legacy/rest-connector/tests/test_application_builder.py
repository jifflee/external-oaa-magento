"""
Tests for core.application_builder.ApplicationBuilder.

oaaclient is required; the whole module is skipped if it is not installed.
"""

import pytest

oaaclient = pytest.importorskip("oaaclient")

from core.application_builder import ApplicationBuilder  # noqa: E402


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------


def _make_entities(
    company_id="2",
    company_name="Acme Corp",
    users=None,
    teams=None,
    roles=None,
):
    company = {
        "id": company_id,
        "name": company_name,
        "legal_name": "Acme Corporation LLC",
        "email": "info@acme.com",
        "admin_email": "admin@acme.com",
        "super_user_id": 10,
    }
    if users is None:
        users = [
            {
                "email": "admin@acme.com",
                "firstname": "John",
                "lastname": "Admin",
                "job_title": "CEO",
                "telephone": "555-0001",
                "is_active": True,
                "is_company_admin": True,
                "company_id": company_id,
                "team_id": None,
                "role_id": "1",
                "role_name": "Company Administrator",
                "magento_customer_id": "10",
            },
            {
                "email": "user1@acme.com",
                "firstname": "Alice",
                "lastname": "Smith",
                "job_title": "Buyer",
                "telephone": "555-0002",
                "is_active": True,
                "is_company_admin": False,
                "company_id": company_id,
                "team_id": None,
                "role_id": "2",
                "role_name": "Default User",
                "magento_customer_id": "11",
            },
        ]
    if teams is None:
        teams = [
            {
                "id": "1",
                "name": "Engineering",
                "description": "Engineering team",
                "company_id": company_id,
                "_structure_id": 3,
            }
        ]
    if roles is None:
        roles = [
            {
                "id": "1",
                "name": "Company Administrator",
                "company_id": company_id,
                "permissions": [
                    {"resource_id": "Magento_Company::index", "permission": "allow"},
                    {"resource_id": "Magento_Sales::all", "permission": "allow"},
                ],
            },
            {
                "id": "2",
                "name": "Default User",
                "company_id": company_id,
                "permissions": [
                    {"resource_id": "Magento_Company::index", "permission": "allow"},
                ],
            },
        ]
    return {
        "company": company,
        "users": users,
        "teams": teams,
        "roles": roles,
        "hierarchy": [],
        "admin_email": "admin@acme.com",
    }


@pytest.fixture()
def builder():
    return ApplicationBuilder(store_url="https://store.acme.com", debug=False)


@pytest.fixture()
def entities():
    return _make_entities()


@pytest.fixture()
def app(builder, entities):
    return builder.build(entities)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildCreatesApplication:
    def test_build_returns_custom_application(self, app):
        from oaaclient.templates import CustomApplication
        assert isinstance(app, CustomApplication)

    def test_app_name_contains_company_id(self, app):
        assert "2" in app.name

    def test_app_application_type(self, app):
        assert app.application_type == "Magento B2B"

    def test_app_description_contains_company_name(self, app):
        assert "Acme Corp" in app.description


class TestBuildAddsUsers:
    def test_user_count(self, app, entities):
        assert len(app.local_users) == len(entities["users"])

    def test_admin_user_present(self, app):
        assert "admin@acme.com" in app.local_users

    def test_regular_user_present(self, app):
        assert "user1@acme.com" in app.local_users

    def test_user_first_name(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.first_name == "John"

    def test_user_last_name(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.last_name == "Admin"

    def test_user_is_active(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.is_active is True

    def test_user_email(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.email == "admin@acme.com"

    def test_user_has_identity(self, app):
        admin = app.local_users["admin@acme.com"]
        assert "admin@acme.com" in admin.identities

    def test_inactive_user_marked_inactive(self, builder):
        entities = _make_entities(
            users=[
                {
                    "email": "inactive@acme.com",
                    "firstname": "Old",
                    "lastname": "User",
                    "job_title": "",
                    "telephone": "",
                    "is_active": False,
                    "is_company_admin": False,
                    "company_id": "2",
                    "team_id": None,
                    "role_id": None,
                    "role_name": None,
                    "magento_customer_id": "99",
                }
            ]
        )
        built_app = builder.build(entities)
        user = built_app.local_users["inactive@acme.com"]
        assert user.is_active is False


class TestBuildAddsCompanyGroup:
    def test_company_group_exists(self, app):
        assert "company_2" in app.local_groups

    def test_company_group_name(self, app):
        group = app.local_groups["company_2"]
        assert group.name == "Acme Corp"


class TestBuildAddsTeamGroups:
    def test_team_group_exists(self, app):
        assert "team_1" in app.local_groups

    def test_team_group_name(self, app):
        group = app.local_groups["team_1"]
        assert group.name == "Engineering"

    def test_multiple_teams_all_added(self, builder):
        entities = _make_entities(
            teams=[
                {"id": "1", "name": "Engineering", "description": "Eng", "company_id": "2", "_structure_id": 3},
                {"id": "2", "name": "Finance", "description": "Fin", "company_id": "2", "_structure_id": 4},
            ]
        )
        built_app = builder.build(entities)
        assert "team_1" in built_app.local_groups
        assert "team_2" in built_app.local_groups

    def test_no_teams_produces_only_company_group(self, builder):
        entities = _make_entities(teams=[])
        built_app = builder.build(entities)
        # Only the company group should be present (no team groups)
        assert "company_2" in built_app.local_groups
        team_groups = [k for k in built_app.local_groups if k.startswith("team_")]
        assert len(team_groups) == 0


class TestBuildAddsRoles:
    def test_role_count(self, app, entities):
        assert len(app.local_roles) == len(entities["roles"])

    def test_admin_role_present(self, app):
        assert "role_2_1" in app.local_roles

    def test_default_user_role_present(self, app):
        assert "role_2_2" in app.local_roles

    def test_role_name(self, app):
        role = app.local_roles["role_2_1"]
        assert role.name == "Company Administrator"

    def test_no_roles_produces_empty_roles(self, builder):
        entities = _make_entities(roles=[])
        built_app = builder.build(entities)
        assert len(built_app.local_roles) == 0


class TestBuildUserProperties:
    def test_job_title_property(self, app):
        admin = app.local_users["admin@acme.com"]
        # Properties are stored in a dict-like structure; check via get_property or properties dict
        props = admin.properties
        assert props.get("job_title") == "CEO"

    def test_telephone_property(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.properties.get("telephone") == "555-0001"

    def test_is_company_admin_property(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.properties.get("is_company_admin") is True

    def test_magento_customer_id_property(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.properties.get("magento_customer_id") == "10"

    def test_company_id_property(self, app):
        admin = app.local_users["admin@acme.com"]
        assert admin.properties.get("company_id") == "2"

    def test_user_without_job_title_does_not_set_property(self, builder):
        """job_title is only set when non-empty."""
        entities = _make_entities(
            users=[
                {
                    "email": "bare@acme.com",
                    "firstname": "Bare",
                    "lastname": "User",
                    "job_title": "",  # empty - should not set property
                    "telephone": "",
                    "is_active": True,
                    "is_company_admin": False,
                    "company_id": "2",
                    "team_id": None,
                    "role_id": None,
                    "role_name": None,
                    "magento_customer_id": "50",
                }
            ]
        )
        built_app = builder.build(entities)
        user = built_app.local_users["bare@acme.com"]
        # job_title property should not be present / should be empty or absent
        props = user.properties
        assert not props.get("job_title")

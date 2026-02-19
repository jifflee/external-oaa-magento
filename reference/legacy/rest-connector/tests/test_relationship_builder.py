"""
Tests for core.relationship_builder.RelationshipBuilder.

oaaclient is required; the whole module is skipped if it is not installed.
"""

import pytest

oaaclient = pytest.importorskip("oaaclient")

from core.application_builder import ApplicationBuilder  # noqa: E402
from core.relationship_builder import RelationshipBuilder  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPANY_ID = "2"
STORE_URL = "https://store.acme.com"


def _build_app(entities):
    """Build an OAA CustomApplication from entities without relationships."""
    builder = ApplicationBuilder(store_url=STORE_URL, debug=False)
    return builder.build(entities)


def _base_entities(extra_users=None, teams=None, roles=None, hierarchy=None):
    company = {
        "id": COMPANY_ID,
        "name": "Acme Corp",
        "legal_name": "Acme Corporation LLC",
        "email": "info@acme.com",
        "admin_email": "admin@acme.com",
        "super_user_id": 10,
    }
    users = [
        {
            "email": "admin@acme.com",
            "firstname": "John",
            "lastname": "Admin",
            "job_title": "CEO",
            "telephone": "555-0001",
            "is_active": True,
            "is_company_admin": True,
            "company_id": COMPANY_ID,
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
            "company_id": COMPANY_ID,
            "team_id": None,
            "role_id": "2",
            "role_name": "Default User",
            "magento_customer_id": "11",
        },
    ]
    if extra_users:
        users.extend(extra_users)

    if teams is None:
        teams = [
            {
                "id": "1",
                "name": "Engineering",
                "description": "Engineering team",
                "company_id": COMPANY_ID,
                "_structure_id": 3,
            }
        ]

    if roles is None:
        roles = [
            {
                "id": "1",
                "name": "Company Administrator",
                "company_id": COMPANY_ID,
                "permissions": [
                    {"resource_id": "Magento_Company::index", "permission": "allow"},
                    {"resource_id": "Magento_Sales::all", "permission": "allow"},
                    {"resource_id": "Magento_Sales::place_order", "permission": "allow"},
                    # deny entry — must NOT be added as a permission
                    {"resource_id": "Magento_NegotiableQuote::all", "permission": "deny"},
                ],
            },
            {
                "id": "2",
                "name": "Default User",
                "company_id": COMPANY_ID,
                "permissions": [
                    {"resource_id": "Magento_Company::index", "permission": "allow"},
                ],
            },
        ]

    if hierarchy is None:
        hierarchy = []

    return {
        "company": company,
        "users": users,
        "teams": teams,
        "roles": roles,
        "hierarchy": hierarchy,
        "admin_email": "admin@acme.com",
    }


@pytest.fixture()
def rel_builder():
    return RelationshipBuilder(debug=False)


# ---------------------------------------------------------------------------
# Tests: user -> company membership
# ---------------------------------------------------------------------------


class TestBuildUserCompanyMembership:
    def test_admin_is_in_company_group(self, rel_builder):
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        admin = app.local_users["admin@acme.com"]
        assert "company_2" in admin.groups

    def test_regular_user_is_in_company_group(self, rel_builder):
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        user1 = app.local_users["user1@acme.com"]
        assert "company_2" in user1.groups

    def test_all_users_in_company_group(self, rel_builder):
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        company_uid = "company_2"
        for email in ("admin@acme.com", "user1@acme.com"):
            local_user = app.local_users[email]
            assert company_uid in local_user.groups, f"{email} not in company group"


# ---------------------------------------------------------------------------
# Tests: user -> role assignment
# ---------------------------------------------------------------------------


class TestBuildUserRoleAssignment:
    def test_admin_gets_role_1(self, rel_builder):
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        admin = app.local_users["admin@acme.com"]
        assert "role_2_1" in admin.roles

    def test_regular_user_gets_role_2(self, rel_builder):
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        user1 = app.local_users["user1@acme.com"]
        assert "role_2_2" in user1.roles

    def test_no_role_when_role_id_is_none(self, rel_builder):
        """Users with role_id=None should not be assigned any role."""
        entities = _base_entities()
        # Clear all role assignments
        for user in entities["users"]:
            user["role_id"] = None
            user["role_name"] = None

        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        for email in ("admin@acme.com", "user1@acme.com"):
            local_user = app.local_users[email]
            assert len(local_user.roles) == 0, f"{email} should have no role"


# ---------------------------------------------------------------------------
# Tests: role -> permission (allow only)
# ---------------------------------------------------------------------------


class TestBuildRolePermissionsAllowOnly:
    def test_allow_permissions_added_to_role(self, rel_builder):
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        admin_role = app.local_roles["role_2_1"]
        # "Magento_Company::index" and "Magento_Sales::all" are allow
        assert "Magento_Company::index" in admin_role.permissions
        assert "Magento_Sales::all" in admin_role.permissions

    def test_deny_permission_not_added_to_role(self, rel_builder):
        """deny entries in permissions must not be added to the OAA role."""
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        admin_role = app.local_roles["role_2_1"]
        # "Magento_NegotiableQuote::all" is deny in the admin role fixture
        assert "Magento_NegotiableQuote::all" not in admin_role.permissions

    def test_unknown_resource_id_ignored(self, rel_builder):
        """resource_ids not in MAGENTO_ACL_PERMISSIONS catalog are silently skipped."""
        entities = _base_entities(
            roles=[
                {
                    "id": "1",
                    "name": "CustomRole",
                    "company_id": COMPANY_ID,
                    "permissions": [
                        {"resource_id": "Magento_Unknown::fake_perm", "permission": "allow"},
                        {"resource_id": "Magento_Company::index", "permission": "allow"},
                    ],
                }
            ]
        )
        app = _build_app(entities)
        # Should not raise
        rel_builder.build_all(app, entities)
        role = app.local_roles["role_2_1"]
        assert "Magento_Company::index" in role.permissions
        assert "Magento_Unknown::fake_perm" not in role.permissions


# ---------------------------------------------------------------------------
# Tests: team -> company parent
# ---------------------------------------------------------------------------


class TestBuildTeamCompanyParent:
    def test_team_is_child_of_company_group(self, rel_builder):
        entities = _base_entities()
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        company_group = app.local_groups["company_2"]
        assert "team_1" in company_group.groups

    def test_multiple_teams_added_to_company(self, rel_builder):
        entities = _base_entities(
            teams=[
                {"id": "1", "name": "Engineering", "description": "", "company_id": COMPANY_ID, "_structure_id": 3},
                {"id": "2", "name": "Finance", "description": "", "company_id": COMPANY_ID, "_structure_id": 4},
            ]
        )
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        company_group = app.local_groups["company_2"]
        assert "team_1" in company_group.groups
        assert "team_2" in company_group.groups

    def test_no_teams_does_not_raise(self, rel_builder):
        entities = _base_entities(teams=[])
        app = _build_app(entities)
        rel_builder.build_all(app, entities)  # should not raise

        company_group = app.local_groups["company_2"]
        team_children = [g for g in company_group.groups if g.startswith("team_")]
        assert len(team_children) == 0


# ---------------------------------------------------------------------------
# Tests: user -> team (from hierarchy links)
# ---------------------------------------------------------------------------


class TestUserTeamFromHierarchy:
    def _make_hierarchy_links(self):
        """Simulate: customer-11 is a child of team-1."""
        return [
            {
                "child_type": "Customer",
                "child_entity": {"entity_id": 11, "entity_type": "customer", "structure_id": 4},
                "parent_type": "CompanyTeam",
                "parent_entity": {"entity_id": 1, "entity_type": "team", "structure_id": 3},
            }
        ]

    def test_user_assigned_to_team_group(self, rel_builder):
        entities = _base_entities(hierarchy=self._make_hierarchy_links())
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        user1 = app.local_users["user1@acme.com"]
        assert "team_1" in user1.groups

    def test_user_not_in_hierarchy_not_added_to_team(self, rel_builder):
        """Admin (id=10) is not in the team hierarchy link, so not in team_1."""
        entities = _base_entities(hierarchy=self._make_hierarchy_links())
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        admin = app.local_users["admin@acme.com"]
        assert "team_1" not in admin.groups

    def test_empty_hierarchy_no_team_membership(self, rel_builder):
        entities = _base_entities(hierarchy=[])
        app = _build_app(entities)
        rel_builder.build_all(app, entities)

        for email in ("admin@acme.com", "user1@acme.com"):
            local_user = app.local_users[email]
            team_groups = [g for g in local_user.groups if g.startswith("team_")]
            assert len(team_groups) == 0, f"{email} should not be in any team"


# ---------------------------------------------------------------------------
# Tests: no_role_when_none (combined scenario)
# ---------------------------------------------------------------------------


class TestNoRoleWhenNone:
    def test_build_all_with_no_roles_does_not_raise(self, rel_builder):
        entities = _base_entities(roles=[])
        # Rebuild users without role_id to avoid referencing missing roles
        for user in entities["users"]:
            user["role_id"] = None
            user["role_name"] = None

        app = _build_app(entities)
        rel_builder.build_all(app, entities)  # should not raise

    def test_user_with_role_id_pointing_to_nonexistent_role(self, rel_builder):
        """If role_id references a non-existent role UID, it should silently skip."""
        entities = _base_entities(roles=[])
        # Keep role_id set but roles list is empty — the UID won't exist in app.local_roles
        entities["users"][0]["role_id"] = "99"
        app = _build_app(entities)
        rel_builder.build_all(app, entities)  # should not raise

        admin = app.local_users["admin@acme.com"]
        assert len(admin.roles) == 0

"""Tests for core.entity_extractor (Commerce Cloud REST).

The entity extractor is identical to the magento-rest on-prem version;
these tests verify that the shared logic behaves correctly when imported from
the commerce-cloud-rest connector's core package.

REST-specific characteristics exercised here:
  - Status is numeric (1=active, 0=inactive)
  - Hierarchy is a nested tree, not a flat items list
  - User-role link is NOT available via REST (role_id is None for non-admin users)
  - Team details come from separate per-team fixtures
"""

import json
import os
import pytest

from core.entity_extractor import EntityExtractor

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "rest_responses")


def load_fixture(filename):
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def current_user():
    return load_fixture("customers_me.json")


@pytest.fixture
def company():
    return load_fixture("company_2.json")


@pytest.fixture
def roles():
    return load_fixture("company_roles.json")


@pytest.fixture
def hierarchy():
    return load_fixture("hierarchy.json")


@pytest.fixture
def team_details():
    team_1 = load_fixture("team_1.json")
    return {1: team_1}


@pytest.fixture
def entities(current_user, company, roles, hierarchy, team_details):
    extractor = EntityExtractor(debug=False)
    return extractor.extract(current_user, company, roles, hierarchy, team_details)


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

class TestCompanyExtraction:
    def test_company_id(self, entities):
        assert entities["company"]["id"] == "2"

    def test_company_name(self, entities):
        assert entities["company"]["name"] == "Acme Corp"

    def test_company_legal_name(self, entities):
        assert entities["company"]["legal_name"] == "Acme Corporation LLC"

    def test_company_email(self, entities):
        assert entities["company"]["email"] == "info@acme.com"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class TestUserExtraction:
    def test_users_present(self, entities):
        assert len(entities["users"]) >= 1

    def test_admin_user_present(self, entities):
        emails = {u["email"] for u in entities["users"]}
        assert "admin@acme.com" in emails

    def test_user_fields_present(self, entities):
        for user in entities["users"]:
            assert "email" in user
            assert "firstname" in user
            assert "lastname" in user
            assert "is_active" in user
            assert "is_company_admin" in user
            assert "company_id" in user
            assert "magento_customer_id" in user

    def test_admin_user_is_active(self, entities):
        users_by_email = {u["email"]: u for u in entities["users"]}
        assert users_by_email["admin@acme.com"]["is_active"] is True

    def test_admin_user_is_company_admin(self, entities):
        users_by_email = {u["email"]: u for u in entities["users"]}
        assert users_by_email["admin@acme.com"]["is_company_admin"] is True

    def test_admin_user_magento_id(self, entities):
        users_by_email = {u["email"]: u for u in entities["users"]}
        assert users_by_email["admin@acme.com"]["magento_customer_id"] == "10"

    def test_non_admin_users_have_no_role_id(self, entities):
        """REST API does not expose role_id for most users - this is the known gap."""
        non_admin_users = [u for u in entities["users"] if not u.get("is_company_admin")]
        for user in non_admin_users:
            assert user.get("role_id") is None

    def test_user_company_id_matches(self, entities):
        for user in entities["users"]:
            assert user["company_id"] == "2"


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class TestTeamExtraction:
    def test_team_present(self, entities):
        assert len(entities["teams"]) == 1

    def test_team_fields(self, entities):
        team = entities["teams"][0]
        assert team["id"] == "1"
        assert team["name"] == "Engineering"
        assert team["description"] == "Engineering team"
        assert team["company_id"] == "2"


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class TestRoleExtraction:
    def test_roles_count(self, entities):
        assert len(entities["roles"]) == 3

    def test_role_names(self, entities):
        names = {r["name"] for r in entities["roles"]}
        assert "Company Administrator" in names
        assert "Default User" in names
        assert "Purchaser" in names

    def test_role_fields(self, entities):
        for role in entities["roles"]:
            assert "id" in role
            assert "name" in role
            assert "company_id" in role
            assert "permissions" in role

    def test_role_company_id(self, entities):
        for role in entities["roles"]:
            assert role["company_id"] == "2"


# ---------------------------------------------------------------------------
# Hierarchy links
# ---------------------------------------------------------------------------

class TestHierarchyExtraction:
    def test_hierarchy_links_produced(self, entities):
        assert len(entities["hierarchy"]) >= 1

    def test_hierarchy_link_fields(self, entities):
        for link in entities["hierarchy"]:
            assert "child_type" in link
            assert "child_entity" in link
            assert "parent_type" in link
            assert "parent_entity" in link


# ---------------------------------------------------------------------------
# Admin email derivation
# ---------------------------------------------------------------------------

class TestAdminEmail:
    def test_admin_email_derived(self, entities):
        assert entities["admin_email"] == "admin@acme.com"

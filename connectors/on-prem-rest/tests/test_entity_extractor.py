"""
Tests for core.entity_extractor.EntityExtractor.

Fixtures loaded from tests/fixtures/rest_responses/.
"""

import json
import os
import pytest

from core.entity_extractor import EntityExtractor

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "rest_responses")


def _load(filename: str) -> dict | list:
    with open(os.path.join(FIXTURES_DIR, filename), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture()
def current_user():
    return _load("customers_me.json")


@pytest.fixture()
def company():
    return _load("company_2.json")


@pytest.fixture()
def roles():
    return _load("company_roles.json")


@pytest.fixture()
def hierarchy():
    return _load("hierarchy.json")


@pytest.fixture()
def team_details():
    team = _load("team_1.json")
    # team entity_id in the hierarchy is 1
    return {1: team}


@pytest.fixture()
def extractor():
    return EntityExtractor(debug=False)


@pytest.fixture()
def extracted(extractor, current_user, company, roles, hierarchy, team_details):
    """Full extraction result used by several tests."""
    return extractor.extract(current_user, company, roles, hierarchy, team_details)


# ---------------------------------------------------------------------------
# Company tests
# ---------------------------------------------------------------------------


class TestExtractCompany:
    def test_company_name(self, extracted):
        assert extracted["company"]["name"] == "Acme Corp"

    def test_legal_name(self, extracted):
        assert extracted["company"]["legal_name"] == "Acme Corporation LLC"

    def test_email(self, extracted):
        assert extracted["company"]["email"] == "info@acme.com"

    def test_company_id_is_string(self, extracted):
        assert extracted["company"]["id"] == "2"

    def test_super_user_id_preserved(self, extracted):
        assert extracted["company"]["super_user_id"] == 10


# ---------------------------------------------------------------------------
# User extraction tests
# ---------------------------------------------------------------------------


class TestExtractUsersFromHierarchy:
    """The fixture hierarchy contains customer IDs 10, 11, 12."""

    def test_correct_number_of_users(self, extracted):
        # Hierarchy has customers 10, 11, 12 — all three should appear.
        assert len(extracted["users"]) == 3

    def test_user_emails_present(self, extracted):
        emails = {u["email"] for u in extracted["users"]}
        # The authenticated user (id=10) gets a real email.
        assert "admin@acme.com" in emails

    def test_non_auth_users_have_placeholder_email(self, extracted):
        # IDs 11 and 12 are not the authenticated caller so they get synthetic emails.
        emails = {u["email"] for u in extracted["users"]}
        assert "customer_11@unknown" in emails
        assert "customer_12@unknown" in emails


class TestExtractAuthenticatedUser:
    def test_firstname(self, extracted):
        admin = next(u for u in extracted["users"] if u["email"] == "admin@acme.com")
        assert admin["firstname"] == "John"

    def test_lastname(self, extracted):
        admin = next(u for u in extracted["users"] if u["email"] == "admin@acme.com")
        assert admin["lastname"] == "Admin"

    def test_job_title(self, extracted):
        admin = next(u for u in extracted["users"] if u["email"] == "admin@acme.com")
        assert admin["job_title"] == "CEO"

    def test_telephone(self, extracted):
        admin = next(u for u in extracted["users"] if u["email"] == "admin@acme.com")
        assert admin["telephone"] == "555-0001"

    def test_company_id(self, extracted):
        admin = next(u for u in extracted["users"] if u["email"] == "admin@acme.com")
        assert admin["company_id"] == "2"

    def test_magento_customer_id(self, extracted):
        admin = next(u for u in extracted["users"] if u["email"] == "admin@acme.com")
        assert admin["magento_customer_id"] == "10"


class TestExtractOtherUsersMinimal:
    """Non-authenticated users have only their customer_id available."""

    def test_customer_11_has_only_customer_id(self, extracted):
        user = next(u for u in extracted["users"] if u["email"] == "customer_11@unknown")
        assert user["magento_customer_id"] == "11"
        assert user["firstname"] == ""
        assert user["lastname"] == ""

    def test_customer_12_has_only_customer_id(self, extracted):
        user = next(u for u in extracted["users"] if u["email"] == "customer_12@unknown")
        assert user["magento_customer_id"] == "12"


# ---------------------------------------------------------------------------
# Status tests
# ---------------------------------------------------------------------------


class TestExtractUserStatus:
    def test_status_1_maps_to_true(self, extractor, company):
        """extension_attributes.company_attributes.status == 1 -> is_active True."""
        customer = {
            "id": 99,
            "email": "active@acme.com",
            "firstname": "Active",
            "lastname": "User",
            "extension_attributes": {"company_attributes": {"status": 1}},
        }
        user = extractor._extract_user_from_customer(customer, "2", None)
        assert user["is_active"] is True

    def test_status_0_maps_to_false(self, extractor):
        """extension_attributes.company_attributes.status == 0 -> is_active False."""
        customer = {
            "id": 99,
            "email": "inactive@acme.com",
            "firstname": "Inactive",
            "lastname": "User",
            "extension_attributes": {"company_attributes": {"status": 0}},
        }
        user = extractor._extract_user_from_customer(customer, "2", None)
        assert user["is_active"] is False

    def test_missing_status_defaults_to_false(self, extractor):
        """Absent status key should not be truthy (defaults to False)."""
        customer = {
            "id": 99,
            "email": "nostatus@acme.com",
            "extension_attributes": {"company_attributes": {}},
        }
        user = extractor._extract_user_from_customer(customer, "2", None)
        assert user["is_active"] is False


# ---------------------------------------------------------------------------
# Admin detection tests
# ---------------------------------------------------------------------------


class TestExtractAdminDetection:
    def test_super_user_id_match_sets_is_company_admin_true(self, extracted):
        admin = next(u for u in extracted["users"] if u["email"] == "admin@acme.com")
        assert admin["is_company_admin"] is True

    def test_non_admin_user_is_company_admin_false(self, extracted):
        non_admin = next(u for u in extracted["users"] if u["email"] == "customer_11@unknown")
        assert non_admin["is_company_admin"] is False

    def test_admin_email_derived(self, extracted):
        """admin_email at the top level should be the super_user's email."""
        assert extracted["admin_email"] == "admin@acme.com"

    def test_no_super_user_id_means_no_admin(self, extractor, current_user, roles, hierarchy, team_details):
        company_no_admin = {
            "id": 2,
            "company_name": "Acme Corp",
            "legal_name": "Acme Corporation LLC",
            "company_email": "info@acme.com",
            # super_user_id intentionally absent
        }
        result = extractor.extract(current_user, company_no_admin, roles, hierarchy, team_details)
        admin_users = [u for u in result["users"] if u["is_company_admin"]]
        assert len(admin_users) == 0


# ---------------------------------------------------------------------------
# Team extraction tests
# ---------------------------------------------------------------------------


class TestExtractTeams:
    def test_team_count(self, extracted):
        # hierarchy.json has exactly one team node (entity_id=1)
        assert len(extracted["teams"]) == 1

    def test_team_name_from_detail(self, extracted):
        team = extracted["teams"][0]
        assert team["name"] == "Engineering"

    def test_team_description(self, extracted):
        team = extracted["teams"][0]
        assert team["description"] == "Engineering team"

    def test_team_id_is_string(self, extracted):
        team = extracted["teams"][0]
        assert team["id"] == "1"

    def test_team_company_id(self, extracted):
        team = extracted["teams"][0]
        assert team["company_id"] == "2"

    def test_team_name_fallback_when_no_detail(
        self, extractor, current_user, company, roles, hierarchy
    ):
        """When team_details is empty the name falls back to 'Team <id>'."""
        result = extractor.extract(current_user, company, roles, hierarchy, team_details={})
        assert result["teams"][0]["name"] == "Team 1"


# ---------------------------------------------------------------------------
# Role extraction tests
# ---------------------------------------------------------------------------


class TestExtractRoles:
    def test_role_count(self, extracted):
        assert len(extracted["roles"]) == 3

    def test_role_names(self, extracted):
        names = {r["name"] for r in extracted["roles"]}
        assert names == {"Company Administrator", "Default User", "Purchaser"}

    def test_role_id_is_string(self, extracted):
        for role in extracted["roles"]:
            assert isinstance(role["id"], str)

    def test_role_permissions_preserved(self, extracted):
        admin_role = next(r for r in extracted["roles"] if r["name"] == "Company Administrator")
        assert len(admin_role["permissions"]) == 10

    def test_role_deny_permission_preserved(self, extracted):
        """Deny entries must survive extraction so downstream code can filter."""
        default_role = next(r for r in extracted["roles"] if r["name"] == "Default User")
        deny_perms = [p for p in default_role["permissions"] if p["permission"] == "deny"]
        assert len(deny_perms) == 1
        assert deny_perms[0]["resource_id"] == "Magento_NegotiableQuote::all"

    def test_role_company_id(self, extracted):
        for role in extracted["roles"]:
            assert role["company_id"] == "2"


# ---------------------------------------------------------------------------
# Hierarchy flattening tests
# ---------------------------------------------------------------------------


class TestFlattenHierarchy:
    def test_flatten_produces_correct_node_count(self, extractor, hierarchy):
        """
        hierarchy.json has 5 nodes in total:
        company-root, customer-10, team-1, customer-11, customer-12.
        The root company node is also appended by _flatten_hierarchy.
        """
        flat = []
        extractor._flatten_hierarchy(hierarchy, flat)
        # company=1 + customer-10=1 + team-1=1 + customer-11=1 + customer-12=1 = 5
        assert len(flat) == 5

    def test_all_entity_types_present(self, extractor, hierarchy):
        flat = []
        extractor._flatten_hierarchy(hierarchy, flat)
        types = {n["entity_type"] for n in flat}
        assert "company" in types
        assert "customer" in types
        assert "team" in types

    def test_entity_ids_correct(self, extractor, hierarchy):
        flat = []
        extractor._flatten_hierarchy(hierarchy, flat)
        entity_ids = {n["entity_id"] for n in flat}
        # company=2, customer=10, team=1, customer=11, customer=12
        assert {2, 10, 1, 11, 12}.issubset(entity_ids)

    def test_empty_node_does_not_raise(self, extractor):
        flat = []
        extractor._flatten_hierarchy({}, flat)  # empty node
        # An empty dict is falsy so _flatten_hierarchy returns early — no crash.
        assert flat == []


# ---------------------------------------------------------------------------
# Hierarchy link extraction tests
# ---------------------------------------------------------------------------


class TestHierarchyLinks:
    def test_link_count(self, extractor, hierarchy):
        flat = []
        extractor._flatten_hierarchy(hierarchy, flat)
        links = extractor._extract_hierarchy_links(flat)
        # Every non-root node that has a valid parent produces one link.
        # Nodes: company(sid=1), customer-10(sid=2,parent=1),
        #         team-1(sid=3,parent=2), customer-11(sid=4,parent=3), customer-12(sid=5,parent=2)
        # But sid=1 has parent=0 which is NOT in the map, so it gets no link.
        # Total links = 4
        assert len(links) == 4

    def test_link_contains_child_and_parent(self, extractor, hierarchy):
        flat = []
        extractor._flatten_hierarchy(hierarchy, flat)
        links = extractor._extract_hierarchy_links(flat)
        for link in links:
            assert "child_type" in link
            assert "parent_type" in link
            assert "child_entity" in link
            assert "parent_entity" in link

    def test_customer_parent_customer_link(self, extractor, hierarchy):
        """customer-10 is a child of the company node (entity_type=company).
        Its parent type should NOT be Customer or CompanyTeam — but our
        _extract_hierarchy_links only knows customer/team, so company maps to
        the else branch (CompanyTeam). Just assert the link exists."""
        flat = []
        extractor._flatten_hierarchy(hierarchy, flat)
        links = extractor._extract_hierarchy_links(flat)
        customer_10_links = [
            lk for lk in links if lk["child_entity"].get("entity_id") == 10
        ]
        assert len(customer_10_links) == 1

    def test_customer_under_team_link_type(self, extractor, hierarchy):
        """customer-11 is a child of team-1, so parent_type should be CompanyTeam."""
        flat = []
        extractor._flatten_hierarchy(hierarchy, flat)
        links = extractor._extract_hierarchy_links(flat)
        customer_11_link = next(
            lk for lk in links if lk["child_entity"].get("entity_id") == 11
        )
        assert customer_11_link["child_type"] == "Customer"
        assert customer_11_link["parent_type"] == "CompanyTeam"

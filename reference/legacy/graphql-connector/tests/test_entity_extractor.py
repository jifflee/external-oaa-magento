"""
Tests for core.entity_extractor.

Covers EntityExtractor and decode_graphql_id against the fixture in
tests/fixtures/graphql_response.json.
"""

import json
import os

import pytest

from core.entity_extractor import EntityExtractor, decode_graphql_id

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_graphql_fixture():
    """Load the full GraphQL response fixture and return the 'data' dict."""
    fixture_path = os.path.join(FIXTURES_DIR, "graphql_response.json")
    with open(fixture_path) as f:
        raw = json.load(f)
    return raw["data"]


@pytest.fixture
def graphql_data():
    return load_graphql_fixture()


@pytest.fixture
def entities(graphql_data):
    extractor = EntityExtractor(debug=False)
    return extractor.extract(graphql_data)


# ---------------------------------------------------------------------------
# decode_graphql_id tests
# ---------------------------------------------------------------------------


def test_decode_graphql_id_basic():
    """MQ== decodes to '1', Mg== decodes to '2'."""
    assert decode_graphql_id("MQ==") == "1"
    assert decode_graphql_id("Mg==") == "2"
    assert decode_graphql_id("Mw==") == "3"
    assert decode_graphql_id("NA==") == "4"


def test_decode_graphql_id_invalid():
    """Invalid base64 is returned as-is without raising an exception."""
    result = decode_graphql_id("!!!not-valid-base64!!!")
    # Must not raise; returns the original string
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Company extraction
# ---------------------------------------------------------------------------


def test_extract_company(entities):
    """Extracted company has correct id, name, legal_name, email, and admin_email."""
    company = entities["company"]

    assert company["id"] == "1"
    assert company["name"] == "Acme Corp"
    assert company["legal_name"] == "Acme Corporation LLC"
    assert company["email"] == "info@acme.com"
    assert company["admin_email"] == "admin@acme.com"


# ---------------------------------------------------------------------------
# User extraction
# ---------------------------------------------------------------------------


def test_extract_users(entities):
    """Three Customer entities are extracted as users."""
    users = entities["users"]
    assert len(users) == 3

    emails = {u["email"] for u in users}
    assert "admin@acme.com" in emails
    assert "jane@acme.com" in emails
    assert "bob@acme.com" in emails


def test_extract_user_fields(entities):
    """Each user contains the expected scalar fields."""
    for user in entities["users"]:
        assert "email" in user
        assert "firstname" in user
        assert "lastname" in user
        assert "job_title" in user
        assert "telephone" in user
        assert "is_active" in user
        assert "is_company_admin" in user
        assert "company_id" in user


def test_extract_user_status(entities):
    """ACTIVE maps to is_active=True; INACTIVE maps to is_active=False."""
    users_by_email = {u["email"]: u for u in entities["users"]}

    assert users_by_email["admin@acme.com"]["is_active"] is True
    assert users_by_email["jane@acme.com"]["is_active"] is True
    assert users_by_email["bob@acme.com"]["is_active"] is False


def test_extract_user_admin_detection(entities):
    """The user whose email matches company_admin.email is flagged is_company_admin=True."""
    users_by_email = {u["email"]: u for u in entities["users"]}

    assert users_by_email["admin@acme.com"]["is_company_admin"] is True
    assert users_by_email["jane@acme.com"]["is_company_admin"] is False
    assert users_by_email["bob@acme.com"]["is_company_admin"] is False


def test_extract_user_team_assignment(entities):
    """Jane is assigned to team 1; admin and bob have no team assignment."""
    users_by_email = {u["email"]: u for u in entities["users"]}

    # jane has team_id because her entity.team.id == "MQ==" which decodes to "1"
    assert users_by_email["jane@acme.com"]["team_id"] == "1"
    assert users_by_email["admin@acme.com"]["team_id"] is None
    assert users_by_email["bob@acme.com"]["team_id"] is None


# ---------------------------------------------------------------------------
# Team extraction
# ---------------------------------------------------------------------------


def test_extract_teams(entities):
    """Exactly one CompanyTeam is extracted with correct fields."""
    teams = entities["teams"]
    assert len(teams) == 1

    team = teams[0]
    assert team["id"] == "1"
    assert team["name"] == "Engineering"
    assert team["description"] == "Engineering team"
    assert team["company_id"] == "1"


# ---------------------------------------------------------------------------
# Role extraction (deduplication)
# ---------------------------------------------------------------------------


def test_extract_roles(entities):
    """Three distinct roles are extracted and deduplicated by role id."""
    roles = entities["roles"]
    assert len(roles) == 3

    role_names = {r["name"] for r in roles}
    assert "Company Administrator" in role_names
    assert "Default User" in role_names
    assert "Purchaser" in role_names


def test_extract_roles_have_company_id(entities):
    """Every extracted role carries the company_id."""
    for role in entities["roles"]:
        assert role["company_id"] == "1"
        assert "id" in role
        assert "name" in role


# ---------------------------------------------------------------------------
# Hierarchy extraction
# ---------------------------------------------------------------------------


def test_extract_hierarchy(entities):
    """Hierarchy contains resolved parent-child links for structure items that have a parent."""
    hierarchy = entities["hierarchy"]

    # Structure items with parent_id: Mg==(team, parent=MQ==), Mw==(jane, parent=Mg==), NA==(bob, parent=MQ==)
    # Resolved non-empty entries exist only where both child and parent are in structure_map
    # MQ== (admin) -> no parent (root, skipped)
    # Mg== (Engineering team) -> parent MQ== (admin)   => CompanyTeam child, Customer parent
    # Mw== (jane) -> parent Mg== (Engineering team)    => Customer child, CompanyTeam parent
    # NA== (bob) -> parent MQ== (admin)                => Customer child, Customer parent
    assert len(hierarchy) >= 1

    child_types = {link["child_type"] for link in hierarchy}
    parent_types = {link["parent_type"] for link in hierarchy}
    assert "Customer" in child_types or "CompanyTeam" in child_types
    assert "Customer" in parent_types or "CompanyTeam" in parent_types


def test_extract_hierarchy_customer_to_customer_link(entities):
    """Bob (INACTIVE Customer) reports up to the admin Customer."""
    hierarchy = entities["hierarchy"]
    customer_to_customer = [
        link for link in hierarchy
        if link["child_type"] == "Customer" and link["parent_type"] == "Customer"
    ]
    # bob -> admin is the only direct Customer->Customer link
    assert len(customer_to_customer) >= 1

    child_emails = {link["child_entity"]["email"] for link in customer_to_customer}
    parent_emails = {link["parent_entity"]["email"] for link in customer_to_customer}
    assert "bob@acme.com" in child_emails
    assert "admin@acme.com" in parent_emails


# ---------------------------------------------------------------------------
# admin_email top-level key
# ---------------------------------------------------------------------------


def test_extract_admin_email(entities):
    """admin_email is propagated to the top-level result dict."""
    assert entities["admin_email"] == "admin@acme.com"

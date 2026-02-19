"""Tests for core.entity_extractor."""

import json
import os
import pytest

from core.entity_extractor import EntityExtractor, decode_graphql_id

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_graphql_fixture():
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


def test_decode_graphql_id_basic():
    assert decode_graphql_id("MQ==") == "1"
    assert decode_graphql_id("Mg==") == "2"
    assert decode_graphql_id("Mw==") == "3"
    assert decode_graphql_id("NA==") == "4"


def test_decode_graphql_id_invalid():
    result = decode_graphql_id("!!!not-valid-base64!!!")
    assert isinstance(result, str)


def test_extract_company(entities):
    company = entities["company"]
    assert company["id"] == "1"
    assert company["name"] == "Acme Corp"
    assert company["legal_name"] == "Acme Corporation LLC"
    assert company["email"] == "info@acme.com"
    assert company["admin_email"] == "admin@acme.com"


def test_extract_users(entities):
    users = entities["users"]
    assert len(users) == 3
    emails = {u["email"] for u in users}
    assert "admin@acme.com" in emails
    assert "jane@acme.com" in emails
    assert "bob@acme.com" in emails


def test_extract_user_fields(entities):
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
    users_by_email = {u["email"]: u for u in entities["users"]}
    assert users_by_email["admin@acme.com"]["is_active"] is True
    assert users_by_email["jane@acme.com"]["is_active"] is True
    assert users_by_email["bob@acme.com"]["is_active"] is False


def test_extract_user_admin_detection(entities):
    users_by_email = {u["email"]: u for u in entities["users"]}
    assert users_by_email["admin@acme.com"]["is_company_admin"] is True
    assert users_by_email["jane@acme.com"]["is_company_admin"] is False
    assert users_by_email["bob@acme.com"]["is_company_admin"] is False


def test_extract_user_team_assignment(entities):
    users_by_email = {u["email"]: u for u in entities["users"]}
    assert users_by_email["jane@acme.com"]["team_id"] == "1"
    assert users_by_email["admin@acme.com"]["team_id"] is None
    assert users_by_email["bob@acme.com"]["team_id"] is None


def test_extract_teams(entities):
    teams = entities["teams"]
    assert len(teams) == 1
    team = teams[0]
    assert team["id"] == "1"
    assert team["name"] == "Engineering"
    assert team["description"] == "Engineering team"
    assert team["company_id"] == "1"


def test_extract_roles(entities):
    roles = entities["roles"]
    assert len(roles) == 3
    role_names = {r["name"] for r in roles}
    assert "Company Administrator" in role_names
    assert "Default User" in role_names
    assert "Purchaser" in role_names


def test_extract_roles_have_company_id(entities):
    for role in entities["roles"]:
        assert role["company_id"] == "1"
        assert "id" in role
        assert "name" in role


def test_extract_hierarchy(entities):
    hierarchy = entities["hierarchy"]
    assert len(hierarchy) >= 1
    child_types = {link["child_type"] for link in hierarchy}
    parent_types = {link["parent_type"] for link in hierarchy}
    assert "Customer" in child_types or "CompanyTeam" in child_types
    assert "Customer" in parent_types or "CompanyTeam" in parent_types


def test_extract_hierarchy_customer_to_customer_link(entities):
    hierarchy = entities["hierarchy"]
    customer_to_customer = [
        link for link in hierarchy
        if link["child_type"] == "Customer" and link["parent_type"] == "Customer"
    ]
    assert len(customer_to_customer) >= 1
    child_emails = {link["child_entity"]["email"] for link in customer_to_customer}
    parent_emails = {link["parent_entity"]["email"] for link in customer_to_customer}
    assert "bob@acme.com" in child_emails
    assert "admin@acme.com" in parent_emails


def test_extract_admin_email(entities):
    assert entities["admin_email"] == "admin@acme.com"

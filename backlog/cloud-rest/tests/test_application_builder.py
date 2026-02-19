"""Tests for core.application_builder (Commerce Cloud REST).

Verifies that ApplicationBuilder produces an OAA CustomApplication
with Commerce Cloud REST-specific naming conventions:
  - app_name_prefix: commerce_cloud_rest
  - application_type: Magento B2B Commerce Cloud (REST)
"""

import pytest

oaaclient = pytest.importorskip("oaaclient")

from core.application_builder import ApplicationBuilder  # noqa: E402


def _make_entities(company_id="2", company_name="Acme Corp", users=None, teams=None, roles=None):
    company = {
        "id": company_id,
        "name": company_name,
        "legal_name": "Acme Corporation LLC",
        "email": "info@acme.com",
        "admin_email": "admin@acme.com",
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
                "magento_customer_id": "10",
            },
        ]
    if teams is None:
        teams = [{"id": "1", "name": "Engineering", "description": "Eng", "company_id": company_id}]
    if roles is None:
        roles = [{"id": "1", "name": "Company Administrator", "company_id": company_id}]
    return {
        "company": company,
        "users": users,
        "teams": teams,
        "roles": roles,
        "hierarchy": [],
        "admin_email": "admin@acme.com",
    }


@pytest.fixture()
def app():
    builder = ApplicationBuilder(store_url="https://cloud.acme.com", debug=False)
    return builder.build(_make_entities())


def test_app_name(app):
    assert "commerce_cloud_rest" in app.name
    assert "2" in app.name


def test_app_type(app):
    assert app.application_type == "Magento B2B Commerce Cloud (REST)"


def test_user_present(app):
    assert "admin@acme.com" in app.local_users


def test_company_group(app):
    assert "company_2" in app.local_groups


def test_team_group(app):
    assert "team_1" in app.local_groups


def test_role_present(app):
    assert "role_2_1" in app.local_roles

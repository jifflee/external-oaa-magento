"""
CE Data Builder -- Synthetic B2B structures from real Magento CE customers.

When running against Magento Community Edition (CE), the B2B GraphQL schema
is unavailable (it requires Adobe Commerce). This module builds synthetic B2B
company/team/role/permission structures using real customer identities fetched
from the CE REST API.

The output matches the exact formats consumed by the existing pipeline:
  - build_synthetic_graphql_response() -> dict matching GraphQL extraction format
  - build_synthetic_roles_response()   -> list matching REST /company/role format

The orchestrator calls these in CE mode (--ce-mode) as a drop-in replacement
for Steps 2-3, then proceeds with Steps 4-7 unchanged.

Data definitions (companies, teams, roles, user assignments) are extracted
from extract_ce.py and kept here as the reusable core. extract_ce.py remains
as a standalone dev tool that uses its own copy.
"""

import base64
from typing import Dict, List, Any, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_id(numeric_id) -> str:
    """Encode a numeric ID to base64, matching Magento GraphQL format."""
    return base64.b64encode(str(numeric_id).encode()).decode()


def _generate_email(firstname: str, lastname: str, domain: str) -> str:
    """Generate a realistic email for a synthetic user."""
    return f"{firstname.lower()}.{lastname.lower()}@{domain}"


def _generate_phone(area_code: str, user_index: int) -> str:
    """Generate a phone number."""
    return f"{area_code}-555-{user_index:04d}"


# ---------------------------------------------------------------------------
# 34 Magento B2B ACL permissions (mirrors shared/permissions.py)
# ---------------------------------------------------------------------------

ALL_34_PERMISSIONS = [
    "Magento_Company::index",
    "Magento_Sales::all",
    "Magento_Sales::place_order",
    "Magento_Sales::payment_account",
    "Magento_Sales::view_orders",
    "Magento_Sales::view_orders_sub",
    "Magento_NegotiableQuote::all",
    "Magento_NegotiableQuote::view_quotes",
    "Magento_NegotiableQuote::manage",
    "Magento_NegotiableQuote::checkout",
    "Magento_NegotiableQuote::view_quotes_sub",
    "Magento_PurchaseOrder::all",
    "Magento_PurchaseOrder::view_purchase_orders",
    "Magento_PurchaseOrder::view_purchase_orders_for_subordinates",
    "Magento_PurchaseOrder::view_purchase_orders_for_company",
    "Magento_PurchaseOrder::autoapprove_purchase_order",
    "Magento_PurchaseOrderRule::super_approve_purchase_order",
    "Magento_PurchaseOrderRule::view_approval_rules",
    "Magento_PurchaseOrderRule::manage_approval_rules",
    "Magento_Company::view",
    "Magento_Company::view_account",
    "Magento_Company::edit_account",
    "Magento_Company::view_address",
    "Magento_Company::edit_address",
    "Magento_Company::contacts",
    "Magento_Company::payment_information",
    "Magento_Company::shipping_information",
    "Magento_Company::user_management",
    "Magento_Company::roles_view",
    "Magento_Company::roles_edit",
    "Magento_Company::users_view",
    "Magento_Company::users_edit",
    "Magento_Company::credit",
    "Magento_Company::credit_history",
]


# ---------------------------------------------------------------------------
# Role definitions: 6 roles with explicit allow/deny per permission
# ---------------------------------------------------------------------------

ROLE_DEFINITIONS = {
    "1": {
        "name": "Company Administrator",
        "permissions": {rid: "allow" for rid in ALL_34_PERMISSIONS},
    },
    "2": {
        "name": "Senior Manager",
        "permissions": {
            "Magento_Company::index": "allow",
            "Magento_Sales::all": "allow",
            "Magento_Sales::place_order": "allow",
            "Magento_Sales::payment_account": "allow",
            "Magento_Sales::view_orders": "allow",
            "Magento_Sales::view_orders_sub": "allow",
            "Magento_NegotiableQuote::all": "allow",
            "Magento_NegotiableQuote::view_quotes": "allow",
            "Magento_NegotiableQuote::manage": "allow",
            "Magento_NegotiableQuote::checkout": "allow",
            "Magento_NegotiableQuote::view_quotes_sub": "allow",
            "Magento_PurchaseOrder::all": "allow",
            "Magento_PurchaseOrder::view_purchase_orders": "allow",
            "Magento_PurchaseOrder::view_purchase_orders_for_subordinates": "allow",
            "Magento_PurchaseOrder::view_purchase_orders_for_company": "allow",
            "Magento_PurchaseOrder::autoapprove_purchase_order": "allow",
            "Magento_PurchaseOrderRule::super_approve_purchase_order": "deny",
            "Magento_PurchaseOrderRule::view_approval_rules": "allow",
            "Magento_PurchaseOrderRule::manage_approval_rules": "deny",
            "Magento_Company::view": "allow",
            "Magento_Company::view_account": "allow",
            "Magento_Company::edit_account": "allow",
            "Magento_Company::view_address": "allow",
            "Magento_Company::edit_address": "allow",
            "Magento_Company::contacts": "allow",
            "Magento_Company::payment_information": "allow",
            "Magento_Company::shipping_information": "allow",
            "Magento_Company::user_management": "deny",
            "Magento_Company::roles_view": "allow",
            "Magento_Company::roles_edit": "deny",
            "Magento_Company::users_view": "allow",
            "Magento_Company::users_edit": "deny",
            "Magento_Company::credit": "allow",
            "Magento_Company::credit_history": "allow",
        },
    },
    "3": {
        "name": "Buyer/Purchaser",
        "permissions": {
            "Magento_Company::index": "allow",
            "Magento_Sales::all": "allow",
            "Magento_Sales::place_order": "allow",
            "Magento_Sales::payment_account": "deny",
            "Magento_Sales::view_orders": "allow",
            "Magento_Sales::view_orders_sub": "allow",
            "Magento_NegotiableQuote::all": "deny",
            "Magento_NegotiableQuote::view_quotes": "deny",
            "Magento_NegotiableQuote::manage": "deny",
            "Magento_NegotiableQuote::checkout": "deny",
            "Magento_NegotiableQuote::view_quotes_sub": "deny",
            "Magento_PurchaseOrder::all": "allow",
            "Magento_PurchaseOrder::view_purchase_orders": "allow",
            "Magento_PurchaseOrder::view_purchase_orders_for_subordinates": "allow",
            "Magento_PurchaseOrder::view_purchase_orders_for_company": "deny",
            "Magento_PurchaseOrder::autoapprove_purchase_order": "deny",
            "Magento_PurchaseOrderRule::super_approve_purchase_order": "deny",
            "Magento_PurchaseOrderRule::view_approval_rules": "deny",
            "Magento_PurchaseOrderRule::manage_approval_rules": "deny",
            "Magento_Company::view": "allow",
            "Magento_Company::view_account": "allow",
            "Magento_Company::edit_account": "deny",
            "Magento_Company::view_address": "allow",
            "Magento_Company::edit_address": "deny",
            "Magento_Company::contacts": "allow",
            "Magento_Company::payment_information": "deny",
            "Magento_Company::shipping_information": "allow",
            "Magento_Company::user_management": "deny",
            "Magento_Company::roles_view": "deny",
            "Magento_Company::roles_edit": "deny",
            "Magento_Company::users_view": "deny",
            "Magento_Company::users_edit": "deny",
            "Magento_Company::credit": "deny",
            "Magento_Company::credit_history": "deny",
        },
    },
    "4": {
        "name": "Viewer",
        "permissions": {
            "Magento_Company::index": "allow",
            "Magento_Sales::all": "deny",
            "Magento_Sales::place_order": "deny",
            "Magento_Sales::payment_account": "deny",
            "Magento_Sales::view_orders": "allow",
            "Magento_Sales::view_orders_sub": "deny",
            "Magento_NegotiableQuote::all": "deny",
            "Magento_NegotiableQuote::view_quotes": "allow",
            "Magento_NegotiableQuote::manage": "deny",
            "Magento_NegotiableQuote::checkout": "deny",
            "Magento_NegotiableQuote::view_quotes_sub": "deny",
            "Magento_PurchaseOrder::all": "deny",
            "Magento_PurchaseOrder::view_purchase_orders": "allow",
            "Magento_PurchaseOrder::view_purchase_orders_for_subordinates": "deny",
            "Magento_PurchaseOrder::view_purchase_orders_for_company": "deny",
            "Magento_PurchaseOrder::autoapprove_purchase_order": "deny",
            "Magento_PurchaseOrderRule::super_approve_purchase_order": "deny",
            "Magento_PurchaseOrderRule::view_approval_rules": "allow",
            "Magento_PurchaseOrderRule::manage_approval_rules": "deny",
            "Magento_Company::view": "allow",
            "Magento_Company::view_account": "allow",
            "Magento_Company::edit_account": "deny",
            "Magento_Company::view_address": "allow",
            "Magento_Company::edit_address": "deny",
            "Magento_Company::contacts": "allow",
            "Magento_Company::payment_information": "deny",
            "Magento_Company::shipping_information": "deny",
            "Magento_Company::user_management": "deny",
            "Magento_Company::roles_view": "allow",
            "Magento_Company::roles_edit": "deny",
            "Magento_Company::users_view": "allow",
            "Magento_Company::users_edit": "deny",
            "Magento_Company::credit": "deny",
            "Magento_Company::credit_history": "deny",
        },
    },
    "5": {
        "name": "External Partner",
        "permissions": {
            "Magento_Company::index": "allow",
            "Magento_Sales::all": "deny",
            "Magento_Sales::place_order": "deny",
            "Magento_Sales::payment_account": "deny",
            "Magento_Sales::view_orders": "allow",
            "Magento_Sales::view_orders_sub": "deny",
            "Magento_NegotiableQuote::all": "deny",
            "Magento_NegotiableQuote::view_quotes": "deny",
            "Magento_NegotiableQuote::manage": "deny",
            "Magento_NegotiableQuote::checkout": "deny",
            "Magento_NegotiableQuote::view_quotes_sub": "deny",
            "Magento_PurchaseOrder::all": "deny",
            "Magento_PurchaseOrder::view_purchase_orders": "deny",
            "Magento_PurchaseOrder::view_purchase_orders_for_subordinates": "deny",
            "Magento_PurchaseOrder::view_purchase_orders_for_company": "deny",
            "Magento_PurchaseOrder::autoapprove_purchase_order": "deny",
            "Magento_PurchaseOrderRule::super_approve_purchase_order": "deny",
            "Magento_PurchaseOrderRule::view_approval_rules": "deny",
            "Magento_PurchaseOrderRule::manage_approval_rules": "deny",
            "Magento_Company::view": "allow",
            "Magento_Company::view_account": "allow",
            "Magento_Company::edit_account": "deny",
            "Magento_Company::view_address": "deny",
            "Magento_Company::edit_address": "deny",
            "Magento_Company::contacts": "allow",
            "Magento_Company::payment_information": "deny",
            "Magento_Company::shipping_information": "deny",
            "Magento_Company::user_management": "deny",
            "Magento_Company::roles_view": "deny",
            "Magento_Company::roles_edit": "deny",
            "Magento_Company::users_view": "deny",
            "Magento_Company::users_edit": "deny",
            "Magento_Company::credit": "deny",
            "Magento_Company::credit_history": "deny",
        },
    },
    "6": {
        "name": "Restricted User",
        "permissions": {
            "Magento_Company::index": "allow",
            **{rid: "deny" for rid in ALL_34_PERMISSIONS if rid != "Magento_Company::index"},
        },
    },
}


# ---------------------------------------------------------------------------
# Company definitions
# ---------------------------------------------------------------------------

DEFAULT_COMPANY = {
    "id": "1",
    "name": "Acme Corp",
    "legal_name": "Acme Corporation LLC",
    "email": "info@acmecorp.example.com",
    "status": "APPROVED",
    "street": ["100 Commerce Drive"],
    "city": "San Francisco",
    "region": "CA",
    "postcode": "94105",
    "country_id": "US",
    "telephone": "415-555-0100",
    "email_domain": "acmecorp.example.com",
    "area_code": "415",
}

DEFAULT_TEAMS = {
    "1": {"name": "Sales", "description": "Sales and customer-facing operations"},
    "2": {"name": "Operations", "description": "Internal operations and procurement"},
}

# User slot assignments: each maps a slot to a role_id and optional team_id.
# Real CE customers fill these slots in order; extras get synthetic names.
DEFAULT_USER_SLOTS = [
    # Company admin -- no team, top of hierarchy
    {"role_id": "1", "team_id": None, "job_title": "CEO", "status": "ACTIVE"},
    # Sales team
    {"role_id": "2", "team_id": "1", "job_title": "VP of Sales", "status": "ACTIVE"},
    {"role_id": "3", "team_id": "1", "job_title": "Senior Buyer", "status": "ACTIVE"},
    {"role_id": "4", "team_id": "1", "job_title": "Sales Analyst", "status": "ACTIVE"},
    # Operations team
    {"role_id": "2", "team_id": "2", "job_title": "Operations Director", "status": "ACTIVE"},
    {"role_id": "3", "team_id": "2", "job_title": "Procurement Specialist", "status": "ACTIVE"},
    {"role_id": "5", "team_id": None, "job_title": "External Auditor", "status": "ACTIVE"},
    {"role_id": "6", "team_id": None, "job_title": "Contractor", "status": "INACTIVE"},
]

SYNTHETIC_NAMES = [
    ("John", "Doe"), ("Sarah", "Chen"), ("Michael", "Rodriguez"),
    ("Emily", "Nguyen"), ("David", "Kim"), ("Robert", "Martinez"),
    ("Lisa", "Thompson"), ("James", "Wilson"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_synthetic_graphql_response(
    customers: List[Dict[str, Any]],
    company: Optional[Dict[str, Any]] = None,
    teams: Optional[Dict[str, Dict]] = None,
    user_slots: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """Build a synthetic GraphQL response using real CE customers.

    Maps real customer identities into a B2B company structure that matches
    the format consumed by EntityExtractor.extract().

    Args:
        customers: List of real customer dicts from REST /V1/customers/search.
        company: Company definition dict (defaults to DEFAULT_COMPANY).
        teams: Team definitions dict (defaults to DEFAULT_TEAMS).
        user_slots: User slot assignments (defaults to DEFAULT_USER_SLOTS).

    Returns:
        A dict matching the GraphQL extraction format:
        {"customer": {...}, "company": {"id": ..., "structure": {"items": [...]}}}
    """
    company = company or DEFAULT_COMPANY
    teams = teams or DEFAULT_TEAMS
    user_slots = user_slots or DEFAULT_USER_SLOTS

    company_id = company["id"]
    email_domain = company.get("email_domain", "example.com")
    area_code = company.get("area_code", "555")

    # Resolve each user slot with a real customer or synthetic identity
    resolved_users = []
    for idx, slot in enumerate(user_slots):
        if idx < len(customers):
            cust = customers[idx]
            firstname = cust.get("firstname", f"User{idx}")
            lastname = cust.get("lastname", f"Synth{idx}")
            email = cust.get("email", _generate_email(firstname, lastname, email_domain))
        elif idx < len(SYNTHETIC_NAMES):
            firstname, lastname = SYNTHETIC_NAMES[idx]
            email = _generate_email(firstname, lastname, email_domain)
        else:
            firstname, lastname = f"User{idx}", f"Generated{idx}"
            email = _generate_email(firstname, lastname, email_domain)

        resolved_users.append({
            "email": email,
            "firstname": firstname,
            "lastname": lastname,
            "slot": slot,
            "customer_id": customers[idx].get("id", 1000 + idx) if idx < len(customers) else 1000 + idx,
        })

    if not resolved_users:
        raise ValueError("No customers or user slots to process")

    # First user is always the company admin
    admin = resolved_users[0]

    # Build structure items (flat list matching GraphQL format)
    structure_items = []
    structure_id = 1

    # 1. Company admin at root
    structure_items.append({
        "id": _encode_id(structure_id),
        "parent_id": "",
        "entity": _build_customer_entity(admin, admin["email"], area_code),
    })
    admin_structure_id = structure_id
    structure_id += 1

    # 2. Teams and their members
    for team_id, team_def in teams.items():
        team_structure_id = structure_id
        structure_items.append({
            "id": _encode_id(structure_id),
            "parent_id": _encode_id(admin_structure_id),
            "entity": {
                "__typename": "CompanyTeam",
                "id": _encode_id(team_id),
                "name": team_def["name"],
                "description": team_def["description"],
            },
        })
        structure_id += 1

        # Users assigned to this team
        for user in resolved_users[1:]:  # skip admin (already added)
            if user["slot"]["team_id"] == team_id:
                structure_items.append({
                    "id": _encode_id(structure_id),
                    "parent_id": _encode_id(team_structure_id),
                    "entity": _build_customer_entity(user, admin["email"], area_code),
                })
                structure_id += 1

    # 3. Users with no team (besides admin)
    for user in resolved_users[1:]:
        if user["slot"]["team_id"] is None:
            structure_items.append({
                "id": _encode_id(structure_id),
                "parent_id": _encode_id(admin_structure_id),
                "entity": _build_customer_entity(user, admin["email"], area_code),
            })
            structure_id += 1

    return {
        "customer": {
            "email": admin["email"],
            "firstname": admin["firstname"],
            "lastname": admin["lastname"],
        },
        "company": {
            "id": _encode_id(company_id),
            "name": company["name"],
            "legal_name": company["legal_name"],
            "email": company["email"],
            "company_admin": {
                "email": admin["email"],
                "firstname": admin["firstname"],
                "lastname": admin["lastname"],
            },
            "structure": {
                "items": structure_items,
            },
        },
    }


def build_synthetic_roles_response() -> List[Dict[str, Any]]:
    """Build a synthetic REST roles response matching get_company_roles_rest() format.

    Returns:
        A list of role dicts, each with "id", "role_name", and "permissions" keys.
        This matches the format returned by MagentoGraphQLClient.get_company_roles_rest().
    """
    roles = []
    for role_id, role_def in ROLE_DEFINITIONS.items():
        permissions = []
        for resource_id, permission in role_def["permissions"].items():
            permissions.append({
                "resource_id": resource_id,
                "permission": permission,
            })
        roles.append({
            "id": int(role_id),
            "role_name": role_def["name"],
            "permissions": permissions,
        })
    return roles


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_customer_entity(
    user: Dict[str, Any],
    admin_email: str,
    area_code: str,
) -> Dict[str, Any]:
    """Build a Customer entity for the GraphQL structure tree."""
    slot = user["slot"]
    role_id = slot.get("role_id", "2")
    role_name = ROLE_DEFINITIONS.get(role_id, {}).get("name", "Default User")
    team_id = slot.get("team_id")

    entity = {
        "__typename": "Customer",
        "email": user["email"],
        "firstname": user["firstname"],
        "lastname": user["lastname"],
        "job_title": slot.get("job_title", ""),
        "telephone": _generate_phone(area_code, user.get("customer_id", 0)),
        "status": slot.get("status", "ACTIVE"),
        "role": {
            "id": _encode_id(role_id),
            "name": role_name,
        },
        "team": None,
    }

    if team_id:
        team_def = DEFAULT_TEAMS.get(team_id, {})
        entity["team"] = {
            "id": _encode_id(team_id),
            "name": team_def.get("name", ""),
            "structure_id": _encode_id(team_id),
        }

    return entity

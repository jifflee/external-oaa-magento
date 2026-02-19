#!/usr/bin/env python3
"""
Magento CE Identity Extraction with Synthetic B2B Data.

Authenticates against a Magento CE 2.4.7 instance, fetches real customer
identities, then wraps them in a synthetic B2B company/team/role/permission
structure. Outputs JSON files in the exact formats the connector pipeline
(entity_extractor.py, relationship_builder.py) expects.

Generates a large-scale enterprise dataset: 3 companies, 8 teams, 6 roles,
~28 users with full native Magento identity attributes (customer groups,
store/website IDs, timestamps, status variations, address fields).

This lets us test the full OAA pipeline end-to-end without Adobe Commerce.

Usage:
    python extract_ce.py --admin --url http://localhost       # Admin token (required for customer list)
    python extract_ce.py --admin --debug                      # With verbose output
    python extract_ce.py --admin --output ./output            # Override output dir
"""

import argparse
import base64
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import requests


# ---------------------------------------------------------------------------
# B2B role/permission definitions (mirrors shared/permissions.py)
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
# Role definitions: role_id -> (name, permissions dict)
# 6 roles covering admin, manager, buyer, viewer, external, restricted
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
# Company definitions: 3 companies with full address/status fields
# ---------------------------------------------------------------------------

COMPANY_DEFINITIONS = {
    "1": {
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
    },
    "2": {
        "name": "TechVendors Inc",
        "legal_name": "TechVendors Incorporated",
        "email": "admin@techvendors.example.com",
        "status": "APPROVED",
        "street": ["250 Partner Blvd", "Suite 400"],
        "city": "Austin",
        "region": "TX",
        "postcode": "73301",
        "country_id": "US",
        "telephone": "512-555-0200",
    },
    "3": {
        "name": "NewCo Startup",
        "legal_name": "NewCo Startup Inc",
        "email": "hello@newco.example.com",
        "status": "PENDING",
        "street": ["42 Innovation Way"],
        "city": "Denver",
        "region": "CO",
        "postcode": "80202",
        "country_id": "US",
        "telephone": "720-555-0300",
    },
}

# ---------------------------------------------------------------------------
# Team definitions: 8 teams across 3 companies
# ---------------------------------------------------------------------------

TEAM_DEFINITIONS = {
    "1": {"name": "Sales", "description": "Sales and customer-facing operations", "company_id": "1"},
    "2": {"name": "Operations", "description": "Internal operations and procurement", "company_id": "1"},
    "3": {"name": "Engineering", "description": "Product development and engineering", "company_id": "1"},
    "4": {"name": "Finance", "description": "Financial planning and accounting", "company_id": "1"},
    "5": {"name": "IT Administration", "description": "IT systems and administration", "company_id": "1"},
    "6": {"name": "Consulting", "description": "External consulting engagements", "company_id": "2"},
    "7": {"name": "Support", "description": "Technical support and implementation", "company_id": "2"},
    # NewCo (company 3) has no teams yet — pending company
}

# ---------------------------------------------------------------------------
# Customer groups (native Magento concept)
# ---------------------------------------------------------------------------

CUSTOMER_GROUPS = {
    "0": {"code": "NOT LOGGED IN", "tax_class_id": 3},
    "1": {"code": "General", "tax_class_id": 3},
    "2": {"code": "Wholesale", "tax_class_id": 3},
    "3": {"code": "Retailer", "tax_class_id": 3},
    "4": {"code": "Partner", "tax_class_id": 3},
}

# ---------------------------------------------------------------------------
# User assignments: ~28 users across 3 companies
# Each entry: company_id, role_id, team_id, job_title, status, group_id,
#             gender, dob, created_at, updated_at
# ---------------------------------------------------------------------------

_ACME_USERS = [
    # Company admin — no team, top of hierarchy
    {"company_id": "1", "role_id": "1", "team_id": None, "job_title": "CEO",
     "status": "ACTIVE", "group_id": 1, "gender": 1, "dob": "1970-04-12",
     "created_at": "2024-06-01 08:00:00", "updated_at": "2026-02-10 09:15:00"},
    # Sales team
    {"company_id": "1", "role_id": "2", "team_id": "1", "job_title": "VP of Sales",
     "status": "ACTIVE", "group_id": 2, "gender": 2, "dob": "1978-09-23",
     "created_at": "2024-06-15 10:30:00", "updated_at": "2026-01-20 14:00:00"},
    {"company_id": "1", "role_id": "3", "team_id": "1", "job_title": "Senior Buyer",
     "status": "ACTIVE", "group_id": 2, "gender": 1, "dob": "1985-03-14",
     "created_at": "2024-07-01 09:00:00", "updated_at": "2026-02-01 11:30:00"},
    {"company_id": "1", "role_id": "3", "team_id": "1", "job_title": "Buyer",
     "status": "ACTIVE", "group_id": 1, "gender": 2, "dob": "1990-11-05",
     "created_at": "2024-08-10 13:45:00", "updated_at": "2026-01-15 16:20:00"},
    {"company_id": "1", "role_id": "4", "team_id": "1", "job_title": "Sales Analyst",
     "status": "INACTIVE", "group_id": 1, "gender": 3, "dob": "1992-07-30",
     "created_at": "2024-09-01 08:00:00", "updated_at": "2025-12-01 10:00:00"},
    # Operations team
    {"company_id": "1", "role_id": "2", "team_id": "2", "job_title": "Operations Director",
     "status": "ACTIVE", "group_id": 2, "gender": 1, "dob": "1975-01-18",
     "created_at": "2024-06-15 10:30:00", "updated_at": "2026-02-05 08:45:00"},
    {"company_id": "1", "role_id": "3", "team_id": "2", "job_title": "Procurement Specialist",
     "status": "ACTIVE", "group_id": 1, "gender": 2, "dob": "1988-05-22",
     "created_at": "2024-07-20 11:00:00", "updated_at": "2026-01-28 15:30:00"},
    {"company_id": "1", "role_id": "3", "team_id": "2", "job_title": "Supply Chain Coordinator",
     "status": "INACTIVE", "group_id": 1, "gender": 1, "dob": "1993-08-10",
     "created_at": "2024-10-01 09:00:00", "updated_at": "2025-11-15 12:00:00"},
    {"company_id": "1", "role_id": "4", "team_id": "2", "job_title": "Operations Analyst",
     "status": "ACTIVE", "group_id": 1, "gender": 3, "dob": "1995-02-28",
     "created_at": "2025-01-10 08:30:00", "updated_at": "2026-02-12 10:00:00"},
    # Engineering team
    {"company_id": "1", "role_id": "2", "team_id": "3", "job_title": "VP of Engineering",
     "status": "ACTIVE", "group_id": 2, "gender": 1, "dob": "1980-06-15",
     "created_at": "2024-06-20 09:00:00", "updated_at": "2026-02-15 11:00:00"},
    {"company_id": "1", "role_id": "6", "team_id": "3", "job_title": "Software Engineer",
     "status": "ACTIVE", "group_id": 1, "gender": 2, "dob": "1994-12-03",
     "created_at": "2025-02-01 10:00:00", "updated_at": "2026-02-18 09:30:00"},
    {"company_id": "1", "role_id": "6", "team_id": "3", "job_title": "QA Engineer",
     "status": "ACTIVE", "group_id": 1, "gender": 1, "dob": "1991-04-19",
     "created_at": "2025-03-15 08:00:00", "updated_at": "2026-02-10 14:00:00"},
    # Finance team
    {"company_id": "1", "role_id": "2", "team_id": "4", "job_title": "CFO",
     "status": "ACTIVE", "group_id": 2, "gender": 2, "dob": "1972-10-07",
     "created_at": "2024-06-15 10:00:00", "updated_at": "2026-02-14 16:00:00"},
    {"company_id": "1", "role_id": "4", "team_id": "4", "job_title": "Financial Analyst",
     "status": "ACTIVE", "group_id": 1, "gender": 1, "dob": "1989-08-25",
     "created_at": "2024-11-01 09:00:00", "updated_at": "2026-01-30 11:45:00"},
    {"company_id": "1", "role_id": "4", "team_id": "4", "job_title": "Accounts Payable Clerk",
     "status": "INACTIVE", "group_id": 1, "gender": 2, "dob": "1996-01-14",
     "created_at": "2025-04-01 08:30:00", "updated_at": "2025-10-20 09:00:00"},
    # IT Administration team
    {"company_id": "1", "role_id": "1", "team_id": "5", "job_title": "IT Director",
     "status": "ACTIVE", "group_id": 2, "gender": 1, "dob": "1977-03-30",
     "created_at": "2024-06-20 10:00:00", "updated_at": "2026-02-17 13:00:00"},
    {"company_id": "1", "role_id": "6", "team_id": "5", "job_title": "Systems Administrator",
     "status": "ACTIVE", "group_id": 1, "gender": 3, "dob": "1990-09-12",
     "created_at": "2024-12-01 09:00:00", "updated_at": "2026-02-08 10:30:00"},
    {"company_id": "1", "role_id": "6", "team_id": "5", "job_title": "Help Desk Technician",
     "status": "ACTIVE", "group_id": 1, "gender": 2, "dob": "1997-06-21",
     "created_at": "2025-06-01 08:00:00", "updated_at": "2026-02-01 15:00:00"},
]

_TECHVENDORS_USERS = [
    # Company admin
    {"company_id": "2", "role_id": "1", "team_id": None, "job_title": "Managing Director",
     "status": "ACTIVE", "group_id": 4, "gender": 2, "dob": "1974-11-08",
     "created_at": "2024-09-01 10:00:00", "updated_at": "2026-02-12 11:00:00"},
    # Consulting team
    {"company_id": "2", "role_id": "5", "team_id": "6", "job_title": "Lead Consultant",
     "status": "ACTIVE", "group_id": 4, "gender": 1, "dob": "1982-02-14",
     "created_at": "2024-09-15 09:00:00", "updated_at": "2026-02-10 14:30:00"},
    {"company_id": "2", "role_id": "5", "team_id": "6", "job_title": "Senior Consultant",
     "status": "ACTIVE", "group_id": 4, "gender": 2, "dob": "1986-07-20",
     "created_at": "2024-10-01 10:00:00", "updated_at": "2026-01-25 16:00:00"},
    {"company_id": "2", "role_id": "5", "team_id": "6", "job_title": "Consultant",
     "status": "INACTIVE", "group_id": 4, "gender": 1, "dob": "1991-05-03",
     "created_at": "2025-01-15 08:30:00", "updated_at": "2025-09-30 12:00:00"},
    {"company_id": "2", "role_id": "6", "team_id": "6", "job_title": "Junior Consultant",
     "status": "ACTIVE", "group_id": 4, "gender": 3, "dob": "1998-10-15",
     "created_at": "2025-07-01 09:00:00", "updated_at": "2026-02-15 10:00:00"},
    # Support team
    {"company_id": "2", "role_id": "5", "team_id": "7", "job_title": "Support Manager",
     "status": "ACTIVE", "group_id": 4, "gender": 1, "dob": "1979-12-01",
     "created_at": "2024-09-15 09:30:00", "updated_at": "2026-02-08 15:00:00"},
    {"company_id": "2", "role_id": "5", "team_id": "7", "job_title": "Support Engineer",
     "status": "ACTIVE", "group_id": 4, "gender": 2, "dob": "1993-03-28",
     "created_at": "2025-02-01 10:00:00", "updated_at": "2026-02-14 09:00:00"},
    {"company_id": "2", "role_id": "6", "team_id": "7", "job_title": "Support Technician",
     "status": "ACTIVE", "group_id": 4, "gender": 1, "dob": "1996-08-17",
     "created_at": "2025-05-15 08:00:00", "updated_at": "2026-01-20 11:30:00"},
]

_NEWCO_USERS = [
    # Company admin — pending company, just onboarded
    {"company_id": "3", "role_id": "1", "team_id": None, "job_title": "Founder & CEO",
     "status": "ACTIVE", "group_id": 1, "gender": 1, "dob": "1983-04-25",
     "created_at": "2026-01-20 14:00:00", "updated_at": "2026-02-18 10:00:00"},
    # One pending user, not yet approved
    {"company_id": "3", "role_id": "6", "team_id": None, "job_title": "Co-Founder",
     "status": "INACTIVE", "group_id": 1, "gender": 2, "dob": "1985-09-11",
     "created_at": "2026-02-01 09:00:00", "updated_at": "2026-02-01 09:00:00"},
]

USER_ASSIGNMENTS = _ACME_USERS + _TECHVENDORS_USERS + _NEWCO_USERS

# Synthetic names for when real CE customers don't cover all slots
SYNTHETIC_NAMES = [
    # Acme Corp (18 users)
    ("John", "Doe"), ("Sarah", "Chen"), ("Michael", "Rodriguez"),
    ("Emily", "Nguyen"), ("David", "Kim"), ("Robert", "Martinez"),
    ("Lisa", "Thompson"), ("James", "Wilson"), ("Maria", "Garcia"),
    ("Thomas", "Anderson"), ("Jennifer", "Lee"), ("Kevin", "Brown"),
    ("Patricia", "Davis"), ("Daniel", "Taylor"), ("Amanda", "White"),
    ("Christopher", "Harris"), ("Jessica", "Clark"), ("Brian", "Lewis"),
    # TechVendors Inc (8 users)
    ("Priya", "Sharma"), ("Marcus", "Johnson"), ("Aiko", "Tanaka"),
    ("Carlos", "Reyes"), ("Fatima", "Al-Hassan"), ("Derek", "O'Brien"),
    ("Yuki", "Nakamura"), ("Samuel", "Okafor"),
    # NewCo Startup (2 users)
    ("Ryan", "Mitchell"), ("Sofia", "Petrov"),
]

# Email domains per company
_COMPANY_EMAIL_DOMAINS = {
    "1": "acmecorp.example.com",
    "2": "techvendors.example.com",
    "3": "newco.example.com",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def encode_id(numeric_id) -> str:
    """Encode a numeric ID to base64, matching Magento GraphQL format."""
    return base64.b64encode(str(numeric_id).encode()).decode()


def _generate_email(firstname: str, lastname: str, company_id: str) -> str:
    """Generate a realistic email for a synthetic user."""
    domain = _COMPANY_EMAIL_DOMAINS.get(company_id, "example.com")
    return f"{firstname.lower()}.{lastname.lower()}@{domain}"


def _generate_phone(company_id: str, user_index: int) -> str:
    """Generate a phone number based on company area code."""
    area_codes = {"1": "415", "2": "512", "3": "720"}
    area = area_codes.get(company_id, "555")
    return f"{area}-555-{user_index:04d}"


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------

class MagentoCEExtractor:
    """Fetches real CE customer identities and builds synthetic B2B data."""

    def __init__(self, store_url: str, username: str, password: str,
                 output_dir: str = "./output", debug: bool = False):
        self.store_url = store_url.rstrip("/")
        self.username = username
        self.password = password
        self.output_dir = output_dir
        self.debug = debug
        self._token = None
        self._session = requests.Session()
        self._errors = []

    # -- authentication -----------------------------------------------------

    def authenticate(self) -> str:
        """Get admin bearer token via REST API."""
        url = f"{self.store_url}/rest/V1/integration/admin/token"
        payload = {"username": self.username, "password": self.password}

        if self.debug:
            print(f"  AUTH: POST {url}")

        resp = self._session.post(url, json=payload, timeout=30)
        resp.raise_for_status()

        self._token = resp.json()
        self._session.headers.update({
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        })

        if self.debug:
            print(f"  AUTH: token={self._token[:20]}...")

        return self._token

    # -- GraphQL helper -----------------------------------------------------

    def graphql(self, query: str, variables: dict = None) -> dict:
        """Execute a GraphQL query and return the data dict."""
        url = f"{self.store_url}/graphql"
        body = {"query": query}
        if variables:
            body["variables"] = variables

        if self.debug:
            print(f"  GQL:  POST {url}  ({len(query)} chars)")

        resp = self._session.post(url, json=body, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        if "errors" in result:
            msgs = [e.get("message", str(e)) for e in result["errors"]]
            raise RuntimeError(f"GraphQL errors: {'; '.join(msgs)}")

        return result.get("data", {})

    # -- data fetchers ------------------------------------------------------

    def fetch_store_config(self) -> dict:
        """Fetch store identity metadata via GraphQL."""
        data = self.graphql("query { storeConfig { store_name store_code base_url } }")
        return data.get("storeConfig", {})

    def fetch_all_customers(self) -> list:
        """Fetch all customers via REST admin API."""
        url = f"{self.store_url}/rest/V1/customers/search"
        params = {
            "searchCriteria[pageSize]": 100,
            "searchCriteria[currentPage]": 1,
        }

        if self.debug:
            print(f"  REST: GET {url}")

        resp = self._session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        customers = result.get("items", [])
        if self.debug:
            print(f"  REST: {len(customers)} customers returned")

        return customers

    # -- B2B data synthesis -------------------------------------------------

    def _get_or_synthesize_customer(self, index: int, assignment: dict,
                                    real_customers: list) -> dict:
        """Return a real customer if available, otherwise synthesize one."""
        if index < len(real_customers):
            return real_customers[index]

        # Synthesize from SYNTHETIC_NAMES
        if index < len(SYNTHETIC_NAMES):
            first, last = SYNTHETIC_NAMES[index]
        else:
            first, last = f"User{index}", f"Synth{index}"

        company_id = assignment["company_id"]
        return {
            "id": 1000 + index,
            "email": _generate_email(first, last, company_id),
            "firstname": first,
            "lastname": last,
            "group_id": assignment.get("group_id", 1),
            "store_id": 1,
            "website_id": 1,
            "created_at": assignment.get("created_at", "2025-01-01 00:00:00"),
            "updated_at": assignment.get("updated_at", "2026-02-01 00:00:00"),
            "created_in": "Default Store View",
            "dob": assignment.get("dob"),
            "gender": assignment.get("gender", 3),
        }

    def build_b2b_graphql_response(self, company_id: str, customers: list,
                                   company_users: list) -> dict:
        """Build a synthetic GraphQL VezaExtraction response for one company.

        Output matches the exact shape consumed by core/entity_extractor.py.
        """
        company_def = COMPANY_DEFINITIONS[company_id]
        company_teams = {tid: t for tid, t in TEAM_DEFINITIONS.items()
                         if t["company_id"] == company_id}

        if not company_users:
            raise ValueError(f"No users for company {company_id}")

        # First user in the company is the admin
        admin = company_users[0]
        admin_customer = admin["_customer"]
        admin_email = admin_customer["email"]

        structure_items = []
        structure_id = 1

        # 1. Company admin at root (no parent)
        structure_items.append({
            "id": encode_id(structure_id),
            "parent_id": "",
            "entity": self._build_customer_entity(
                admin_customer, admin["_assignment"], admin_email
            ),
        })
        admin_structure_id = structure_id
        structure_id += 1

        # 2. Teams and their members
        for team_id, team_def in company_teams.items():
            team_structure_id = structure_id
            structure_items.append({
                "id": encode_id(structure_id),
                "parent_id": encode_id(admin_structure_id),
                "entity": {
                    "__typename": "CompanyTeam",
                    "id": encode_id(team_id),
                    "name": team_def["name"],
                    "description": team_def["description"],
                },
            })
            structure_id += 1

            # Add users assigned to this team
            for user_data in company_users:
                if user_data["_assignment"]["team_id"] == team_id:
                    structure_items.append({
                        "id": encode_id(structure_id),
                        "parent_id": encode_id(team_structure_id),
                        "entity": self._build_customer_entity(
                            user_data["_customer"],
                            user_data["_assignment"],
                            admin_email,
                        ),
                    })
                    structure_id += 1

        # 3. Users with no team (besides admin, already added)
        for user_data in company_users[1:]:
            if user_data["_assignment"]["team_id"] is None:
                structure_items.append({
                    "id": encode_id(structure_id),
                    "parent_id": encode_id(admin_structure_id),
                    "entity": self._build_customer_entity(
                        user_data["_customer"],
                        user_data["_assignment"],
                        admin_email,
                    ),
                })
                structure_id += 1

        return {
            "customer": {
                "email": admin_email,
                "firstname": admin_customer["firstname"],
                "lastname": admin_customer["lastname"],
            },
            "company": {
                "id": encode_id(company_id),
                "name": company_def["name"],
                "legal_name": company_def["legal_name"],
                "email": company_def["email"],
                "status": company_def["status"],
                "street": company_def["street"],
                "city": company_def["city"],
                "region": company_def["region"],
                "postcode": company_def["postcode"],
                "country_id": company_def["country_id"],
                "telephone": company_def["telephone"],
                "company_admin": {
                    "email": admin_email,
                    "firstname": admin_customer["firstname"],
                    "lastname": admin_customer["lastname"],
                },
                "structure": {
                    "items": structure_items,
                },
            },
        }

    def _build_customer_entity(self, customer: dict, assignment: dict,
                               admin_email: str) -> dict:
        """Build a Customer entity for the B2B structure with all native attributes."""
        role_id = assignment.get("role_id", "2")
        role_name = ROLE_DEFINITIONS.get(role_id, {}).get("name", "Default User")
        team_id = assignment.get("team_id")

        entity = {
            "__typename": "Customer",
            "email": customer["email"],
            "firstname": customer["firstname"],
            "lastname": customer["lastname"],
            "job_title": assignment.get("job_title", ""),
            "telephone": _generate_phone(
                assignment.get("company_id", "1"),
                customer.get("id", 0),
            ),
            "status": assignment.get("status", "ACTIVE"),
            "role": {
                "id": encode_id(role_id),
                "name": role_name,
            },
            "team": None,
            # Native Magento identity attributes
            "created_at": assignment.get("created_at", "2025-01-01 08:00:00"),
            "updated_at": assignment.get("updated_at", "2026-02-01 12:00:00"),
            "group_id": assignment.get("group_id", 1),
            "store_id": customer.get("store_id", 1),
            "website_id": customer.get("website_id", 1),
            "created_in": customer.get("created_in", "Default Store View"),
            "gender": assignment.get("gender", 3),
            "dob": assignment.get("dob"),
        }

        if team_id:
            team_def = TEAM_DEFINITIONS.get(team_id, {})
            entity["team"] = {
                "id": encode_id(team_id),
                "name": team_def.get("name", ""),
                "structure_id": encode_id(team_id),
            }

        return entity

    def build_rest_roles_response(self) -> dict:
        """Build a synthetic REST /rest/V1/company/role response.

        Output matches the exact shape consumed by core/relationship_builder.py.
        """
        items = []
        for role_id, role_def in ROLE_DEFINITIONS.items():
            permissions = []
            for resource_id, permission in role_def["permissions"].items():
                permissions.append({
                    "resource_id": resource_id,
                    "permission": permission,
                })
            items.append({
                "id": int(role_id),
                "role_name": role_def["name"],
                "permissions": permissions,
            })

        return {
            "items": items,
            "total_count": len(items),
        }

    def build_rest_customers(self, all_users: list) -> dict:
        """Build enriched REST /rest/V1/customers/search response with all native fields."""
        items = []
        for user_data in all_users:
            customer = user_data["_customer"]
            assignment = user_data["_assignment"]
            company_id = assignment["company_id"]

            # REST customer status: 1=Active, 0=Inactive
            rest_status = 1 if assignment.get("status") == "ACTIVE" else 0

            items.append({
                "id": customer.get("id", 0),
                "email": customer["email"],
                "firstname": customer["firstname"],
                "lastname": customer["lastname"],
                "group_id": assignment.get("group_id", 1),
                "store_id": customer.get("store_id", 1),
                "website_id": customer.get("website_id", 1),
                "created_at": assignment.get("created_at", "2025-01-01 00:00:00"),
                "updated_at": assignment.get("updated_at", "2026-02-01 00:00:00"),
                "created_in": customer.get("created_in", "Default Store View"),
                "dob": assignment.get("dob"),
                "gender": assignment.get("gender", 3),
                "extension_attributes": {
                    "company_attributes": {
                        "customer_id": customer.get("id", 0),
                        "company_id": int(company_id),
                        "job_title": assignment.get("job_title", ""),
                        "status": rest_status,
                        "telephone": _generate_phone(company_id, customer.get("id", 0)),
                    }
                },
            })

        return {
            "items": items,
            "total_count": len(items),
        }

    def build_customer_groups_response(self) -> dict:
        """Build REST /rest/V1/customerGroups/search response."""
        items = []
        for group_id, group_def in CUSTOMER_GROUPS.items():
            items.append({
                "id": int(group_id),
                "code": group_def["code"],
                "tax_class_id": group_def["tax_class_id"],
                "tax_class_name": "Retail Customer",
            })
        return {
            "items": items,
            "total_count": len(items),
        }

    # -- output helpers -----------------------------------------------------

    def _ensure_output_dirs(self):
        """Create timestamped output directory."""
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        self._run_dir = Path(self.output_dir) / f"{ts}_b2b_extraction"
        self._raw_dir = self._run_dir / "raw"
        self._raw_dir.mkdir(parents=True, exist_ok=True)

    def _save_json(self, filename: str, data: dict) -> str:
        """Save a JSON file to the run directory root."""
        path = self._run_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        if self.debug:
            print(f"  SAVED: {path}")
        return str(path)

    def _save_raw(self, filename: str, data: dict) -> str:
        """Save a raw JSON response to the raw/ subdirectory."""
        path = self._raw_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        if self.debug:
            print(f"  SAVED: {path}")
        return str(path)

    # -- main orchestrator --------------------------------------------------

    def run(self) -> dict:
        """Run extraction pipeline: real CE data + synthetic B2B structure."""
        started = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        self._ensure_output_dirs()
        self._errors = []

        print(f"\n{'='*60}")
        print("MAGENTO CE IDENTITY + SYNTHETIC B2B EXTRACTION")
        print("=" * 60)
        print(f"Store URL:   {self.store_url}")
        print(f"Output dir:  {self._run_dir}")
        print(f"Companies:   {len(COMPANY_DEFINITIONS)}")
        print(f"Roles:       {len(ROLE_DEFINITIONS)}")
        print(f"Teams:       {len(TEAM_DEFINITIONS)}")
        print(f"Users:       {len(USER_ASSIGNMENTS)}")

        # -- Step 1: Authenticate as admin ----------------------------------
        print(f"\n--- Step 1: Authenticate (admin) ---")
        try:
            self.authenticate()
            print("  OK")
        except Exception as e:
            print(f"  FAILED: {e}")
            self._errors.append({"step": "authenticate", "error": str(e)})
            if self.debug:
                traceback.print_exc()
            return self._build_summary(started, started_at)

        # -- Step 2: Fetch store config (real) ------------------------------
        print(f"\n--- Step 2: Store config (real) ---")
        store_config = {}
        try:
            store_config = self.fetch_store_config()
            self._save_raw("store_config.json", store_config)
            print(f"  OK — {store_config.get('store_name', 'unknown')}")
        except Exception as e:
            print(f"  FAILED: {e}")
            self._errors.append({"step": "store_config", "error": str(e)})
            if self.debug:
                traceback.print_exc()

        # -- Step 3: Fetch all customers (real) -----------------------------
        print(f"\n--- Step 3: Fetch customers via REST (real) ---")
        real_customers = []
        try:
            real_customers = self.fetch_all_customers()
            self._save_raw("customers_rest_real.json", {
                "items": real_customers, "total_count": len(real_customers),
            })
            print(f"  OK — {len(real_customers)} real customers")
            for c in real_customers:
                print(f"    {c['email']} ({c['firstname']} {c['lastname']})")
        except Exception as e:
            print(f"  FAILED: {e}")
            self._errors.append({"step": "fetch_customers", "error": str(e)})
            if self.debug:
                traceback.print_exc()
            return self._build_summary(started, started_at)

        # -- Step 4: Resolve all users (real + synthetic) -------------------
        print(f"\n--- Step 4: Resolve {len(USER_ASSIGNMENTS)} user slots ---")
        all_users = []
        for idx, assignment in enumerate(USER_ASSIGNMENTS):
            customer = self._get_or_synthesize_customer(idx, assignment, real_customers)
            all_users.append({
                "_customer": customer,
                "_assignment": assignment,
            })
        real_used = min(len(real_customers), len(USER_ASSIGNMENTS))
        synth_used = len(USER_ASSIGNMENTS) - real_used
        print(f"  {real_used} real customers used, {synth_used} synthetic generated")

        # Group users by company
        company_user_map = {}
        for user_data in all_users:
            cid = user_data["_assignment"]["company_id"]
            company_user_map.setdefault(cid, []).append(user_data)

        # -- Step 5: Build per-company GraphQL responses --------------------
        print(f"\n--- Step 5: Build per-company B2B GraphQL responses ---")
        graphql_responses = {}
        for company_id in sorted(COMPANY_DEFINITIONS.keys()):
            company_name = COMPANY_DEFINITIONS[company_id]["name"]
            company_users = company_user_map.get(company_id, [])
            try:
                response = self.build_b2b_graphql_response(
                    company_id, real_customers, company_users
                )
                filename = f"b2b_graphql_response_company_{company_id}.json"
                self._save_json(filename, {"data": response})
                graphql_responses[company_id] = response

                items = response["company"]["structure"]["items"]
                user_count = sum(1 for i in items if i["entity"]["__typename"] == "Customer")
                team_count = sum(1 for i in items if i["entity"]["__typename"] == "CompanyTeam")
                status = COMPANY_DEFINITIONS[company_id]["status"]
                print(f"  Company {company_id}: {company_name} ({status})")
                print(f"    {user_count} users, {team_count} teams")

                for item in items:
                    e = item["entity"]
                    if e["__typename"] == "Customer":
                        role = e["role"]["name"]
                        team = e["team"]["name"] if e["team"] else "(no team)"
                        st = e["status"]
                        print(f"      {e['email']:40s} {role:25s} {team:18s} {st}")
                    else:
                        print(f"      [Team] {e['name']:35s} {e['description']}")
            except Exception as e:
                print(f"  FAILED (company {company_id}): {e}")
                self._errors.append({
                    "step": f"build_graphql_company_{company_id}",
                    "error": str(e),
                })
                if self.debug:
                    traceback.print_exc()

        # -- Step 6: Build synthetic REST roles response --------------------
        print(f"\n--- Step 6: Build synthetic REST roles response ---")
        rest_roles = None
        try:
            rest_roles = self.build_rest_roles_response()
            self._save_json("b2b_rest_roles_response.json", rest_roles)

            for role in rest_roles["items"]:
                allow_count = sum(1 for p in role["permissions"] if p["permission"] == "allow")
                deny_count = sum(1 for p in role["permissions"] if p["permission"] == "deny")
                print(f"  {role['role_name']:25s}  allow={allow_count:2d}  deny={deny_count:2d}")
        except Exception as e:
            print(f"  FAILED: {e}")
            self._errors.append({"step": "build_rest_roles", "error": str(e)})
            if self.debug:
                traceback.print_exc()

        # -- Step 7: Build enriched REST customers --------------------------
        print(f"\n--- Step 7: Build enriched REST customers response ---")
        rest_customers = None
        try:
            rest_customers = self.build_rest_customers(all_users)
            self._save_json("customers_rest.json", rest_customers)
            active = sum(1 for i in rest_customers["items"]
                         if i["extension_attributes"]["company_attributes"]["status"] == 1)
            inactive = rest_customers["total_count"] - active
            print(f"  {rest_customers['total_count']} customers ({active} active, {inactive} inactive)")

            # Show group distribution
            group_counts = {}
            for item in rest_customers["items"]:
                gid = item["group_id"]
                gname = CUSTOMER_GROUPS.get(str(gid), {}).get("code", f"Group {gid}")
                group_counts[gname] = group_counts.get(gname, 0) + 1
            for gname, count in sorted(group_counts.items()):
                print(f"    {gname}: {count}")
        except Exception as e:
            print(f"  FAILED: {e}")
            self._errors.append({"step": "build_rest_customers", "error": str(e)})
            if self.debug:
                traceback.print_exc()

        # -- Step 8: Build customer groups ----------------------------------
        print(f"\n--- Step 8: Build customer groups response ---")
        try:
            groups_response = self.build_customer_groups_response()
            self._save_json("customer_groups.json", groups_response)
            for g in groups_response["items"]:
                print(f"  Group {g['id']}: {g['code']}")
        except Exception as e:
            print(f"  FAILED: {e}")
            self._errors.append({"step": "build_customer_groups", "error": str(e)})
            if self.debug:
                traceback.print_exc()

        # -- Save summary ---------------------------------------------------
        summary = self._build_summary(
            started, started_at, real_customers,
            graphql_responses, rest_roles, rest_customers,
        )
        self._save_json("extraction_summary.json", summary)

        print(f"\n{'='*60}")
        print("EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"Output:  {self._run_dir}")
        print(f"Errors:  {len(self._errors)}")
        print(f"Time:    {summary['elapsed_seconds']:.1f}s")
        print(f"\nConnector-ready files:")
        for cid in sorted(COMPANY_DEFINITIONS.keys()):
            cname = COMPANY_DEFINITIONS[cid]["name"]
            print(f"  b2b_graphql_response_company_{cid}.json  -> {cname}")
        print(f"  b2b_rest_roles_response.json             -> all {len(ROLE_DEFINITIONS)} roles")
        print(f"  customers_rest.json                      -> all {len(USER_ASSIGNMENTS)} enriched customers")
        print(f"  customer_groups.json                     -> {len(CUSTOMER_GROUPS)} groups")
        print(f"\nFeed to pipeline:")
        print(f"  EntityExtractor.extract(data['data'])     per company file")
        print(f"  RelationshipBuilder                       with rest_roles + customers_rest")

        return summary

    def _build_summary(self, started, started_at, customers=None,
                       graphql_responses=None, rest_roles=None,
                       rest_customers=None) -> dict:
        elapsed = time.time() - started
        counts = {
            "companies_defined": len(COMPANY_DEFINITIONS),
            "teams_defined": len(TEAM_DEFINITIONS),
            "roles_defined": len(ROLE_DEFINITIONS),
            "permissions_defined": len(ALL_34_PERMISSIONS),
            "user_slots_defined": len(USER_ASSIGNMENTS),
            "customer_groups_defined": len(CUSTOMER_GROUPS),
        }
        if customers:
            counts["customers_real"] = len(customers)
            counts["customers_synthetic"] = max(0, len(USER_ASSIGNMENTS) - len(customers))

        company_details = {}
        if graphql_responses:
            for cid, response in graphql_responses.items():
                items = response.get("company", {}).get("structure", {}).get("items", [])
                users = sum(1 for i in items if i["entity"]["__typename"] == "Customer")
                teams = sum(1 for i in items if i["entity"]["__typename"] == "CompanyTeam")
                company_details[cid] = {
                    "name": COMPANY_DEFINITIONS[cid]["name"],
                    "status": COMPANY_DEFINITIONS[cid]["status"],
                    "users": users,
                    "teams": teams,
                }
            counts["total_users_in_graphql"] = sum(
                d["users"] for d in company_details.values()
            )
            counts["total_teams_in_graphql"] = sum(
                d["teams"] for d in company_details.values()
            )

        if rest_roles:
            counts["roles_in_rest"] = rest_roles.get("total_count", 0)
        if rest_customers:
            counts["customers_in_rest"] = rest_customers.get("total_count", 0)

        # Status distribution
        status_dist = {}
        for assignment in USER_ASSIGNMENTS:
            s = assignment.get("status", "ACTIVE")
            status_dist[s] = status_dist.get(s, 0) + 1

        return {
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "store_url": self.store_url,
            "output_dir": str(self._run_dir),
            "data_source": "CE real customers + synthetic B2B structure",
            "counts": counts,
            "company_details": company_details,
            "user_status_distribution": status_dist,
            "errors": self._errors,
            "success": len(self._errors) == 0,
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Magento CE Identity Extraction with Synthetic B2B Data"
    )
    parser.add_argument("--url", default=None, help="Magento store URL (overrides MAGENTO_STORE_URL)")
    parser.add_argument("--username", default=None, help="Admin username (overrides MAGENTO_ADMIN_USERNAME)")
    parser.add_argument("--password", default=None, help="Admin password (overrides MAGENTO_ADMIN_PASSWORD)")
    parser.add_argument("--admin", action="store_true", default=True, help="Use admin token (default, required)")
    parser.add_argument("--output", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--env", default="./.env", help="Path to .env file (default: ./.env)")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug output")

    args = parser.parse_args()

    # Load .env if present
    env_path = Path(args.env)
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            print(f"Loaded .env from: {env_path}")
        except ImportError:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        value = value.strip().strip("'\"")
                        os.environ.setdefault(key.strip(), value)
            print(f"Loaded .env from: {env_path}  (manual parse)")

    store_url = args.url or os.getenv("MAGENTO_STORE_URL", "http://localhost")
    username = args.username or os.getenv("MAGENTO_ADMIN_USERNAME", os.getenv("MAGENTO_USERNAME", ""))
    password = args.password or os.getenv("MAGENTO_ADMIN_PASSWORD", os.getenv("MAGENTO_PASSWORD", ""))

    if not username or not password:
        print("ERROR: Admin username and password are required.")
        print("  Set MAGENTO_ADMIN_USERNAME / MAGENTO_ADMIN_PASSWORD in .env")
        print("  Or use --username / --password")
        sys.exit(1)

    extractor = MagentoCEExtractor(
        store_url=store_url,
        username=username,
        password=password,
        output_dir=args.output,
        debug=args.debug,
    )

    summary = extractor.run()
    sys.exit(0 if summary.get("success") else 1)


if __name__ == "__main__":
    main()

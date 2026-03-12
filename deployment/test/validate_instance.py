#!/usr/bin/env python3
"""
validate_instance.py — 5-stage validation of a target Adobe Commerce instance.

Confirms connectivity, authentication, B2B module availability, GraphQL
extraction compatibility, and REST role permissions before running the
connector.

Cross-platform: works on Windows, macOS, and Linux.
Prerequisites: Python 3.9+, requests (pip install requests)

Usage:
    # With env vars:
    MAGENTO_URL=https://magento.example.com \
    COMPANY_ADMIN_EMAIL=admin@company.com \
    COMPANY_ADMIN_PASSWORD=secret \
    MAGENTO_ADMIN_USER=admin \
    MAGENTO_ADMIN_PASS=secret \
    python validate_instance.py

    # Interactive (prompts for missing values):
    python validate_instance.py
"""

import json
import os
import sys
from getpass import getpass

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is required. Install with: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Colors:
    """ANSI colors — disabled automatically on Windows without colorama."""
    ENABLED = sys.stdout.isatty() and os.name != "nt"
    RED = "\033[0;31m" if ENABLED else ""
    GREEN = "\033[0;32m" if ENABLED else ""
    YELLOW = "\033[0;33m" if ENABLED else ""
    NC = "\033[0m" if ENABLED else ""


PASS = f"{Colors.GREEN}✓ PASS{Colors.NC}"
FAIL = f"{Colors.RED}✗ FAIL{Colors.NC}"
WARN = f"{Colors.YELLOW}⚠ WARN{Colors.NC}"


def prompt_if_missing(env_var: str, prompt_text: str, secret: bool = False) -> str:
    """Read from env var or prompt interactively."""
    value = os.environ.get(env_var, "").strip()
    if value:
        return value
    if secret:
        return getpass(f"{prompt_text}: ")
    return input(f"{prompt_text}: ").strip()


def print_summary(stages: dict):
    """Print the color-coded validation summary."""
    print()
    print("=" * 40)
    print("VALIDATION SUMMARY")
    print("=" * 40)

    all_pass = True
    for name, (result, detail) in stages.items():
        if result == "PASS":
            symbol = PASS
        elif result == "FAIL":
            symbol = FAIL
            all_pass = False
        elif result == "WARN":
            symbol = WARN
        else:
            symbol = "  SKIP"

        print(f"  Stage: {name:<22s} {symbol}  ({detail})")

    print("=" * 40)
    if all_pass:
        print(f"{Colors.GREEN}Instance is ready for extraction.{Colors.NC}")
        print("Run: python run_extraction.py  (or ./run-extraction.sh)")
    else:
        print(f"{Colors.RED}Validation failed. Fix the issues above and retry.{Colors.NC}")
    print("=" * 40)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    stages: dict[str, tuple[str, str]] = {}

    # -- Collect credentials --------------------------------------------------
    magento_url = prompt_if_missing(
        "MAGENTO_URL", "Magento base URL (e.g. https://magento.example.com)"
    ).rstrip("/")
    company_email = prompt_if_missing("COMPANY_ADMIN_EMAIL", "Company admin email")
    company_pass = prompt_if_missing("COMPANY_ADMIN_PASSWORD", "Company admin password", secret=True)
    admin_user = prompt_if_missing("MAGENTO_ADMIN_USER", "Magento admin username")
    admin_pass = prompt_if_missing("MAGENTO_ADMIN_PASS", "Magento admin password", secret=True)

    # =========================================================================
    # STAGE 1: Connectivity
    # =========================================================================
    print("\nStage 1/5: Connectivity")
    print("---")

    try:
        resp = requests.get(
            f"{magento_url}/rest/V1/store/storeConfigs",
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        store_data = resp.json()
    except requests.exceptions.SSLError as e:
        stages["Connectivity"] = ("FAIL", f"TLS/certificate error: {e}")
        print(f"  {Colors.RED}TLS error. Self-signed cert? Try http:// or verify CA.{Colors.NC}")
        print_summary(stages)
        sys.exit(1)
    except (requests.RequestException, ValueError) as e:
        stages["Connectivity"] = ("FAIL", f"Cannot reach instance: {e}")
        print_summary(stages)
        sys.exit(1)

    if not isinstance(store_data, list) or len(store_data) == 0:
        stages["Connectivity"] = ("FAIL", "Response is not valid JSON array")
        print_summary(stages)
        sys.exit(1)

    base_url = store_data[0].get("base_url", "unknown")
    currency = store_data[0].get("default_display_currency_code", "unknown")
    print(f"  Store URL:      {base_url}")
    print(f"  Base currency:  {currency}")

    stages["Connectivity"] = ("PASS", "reachable")

    # =========================================================================
    # STAGE 2: Authentication (customer token)
    # =========================================================================
    print("\nStage 2/5: Authentication")
    print("---")

    try:
        resp = requests.post(
            f"{magento_url}/rest/V1/integration/customer/token",
            json={"username": company_email, "password": company_pass},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        customer_token = resp.json()
    except requests.RequestException as e:
        stages["Authentication"] = ("FAIL", f"Customer token request failed: {e}")
        print_summary(stages)
        sys.exit(1)

    if isinstance(customer_token, dict) and "message" in customer_token:
        stages["Authentication"] = ("FAIL", f"Auth error: {customer_token['message']}")
        print_summary(stages)
        sys.exit(1)

    if not isinstance(customer_token, str) or len(customer_token) < 10:
        stages["Authentication"] = ("FAIL", "Unexpected token format")
        print_summary(stages)
        sys.exit(1)

    print("  Customer token obtained")
    stages["Authentication"] = ("PASS", "customer token obtained")

    # =========================================================================
    # STAGE 3: B2B Module Check
    # =========================================================================
    print("\nStage 3/5: B2B Module Check")
    print("---")

    # 3a: Admin token
    try:
        resp = requests.post(
            f"{magento_url}/rest/V1/integration/admin/token",
            json={"username": admin_user, "password": admin_pass},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        admin_token = resp.json()
    except requests.RequestException as e:
        stages["B2B Module"] = ("FAIL", f"Admin token failed: {e}")
        print_summary(stages)
        sys.exit(1)

    if isinstance(admin_token, dict) and "message" in admin_token:
        stages["B2B Module"] = ("FAIL", f"Admin auth error: {admin_token['message']}")
        print_summary(stages)
        sys.exit(1)

    print("  Admin token obtained")

    # 3b: REST B2B endpoint
    try:
        resp = requests.get(
            f"{magento_url}/rest/V1/company/role",
            params={"searchCriteria[pageSize]": 1},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        rest_b2b = resp.json()
    except requests.RequestException as e:
        stages["B2B Module"] = ("FAIL", f"REST /company/role error: {e}")
        print_summary(stages)
        sys.exit(1)

    if isinstance(rest_b2b, dict) and "message" in rest_b2b:
        stages["B2B Module"] = ("FAIL", f"REST B2B error: {rest_b2b['message']}")
        print_summary(stages)
        sys.exit(1)

    print("  REST B2B endpoint: OK")

    # 3c: GraphQL B2B query
    try:
        resp = requests.post(
            f"{magento_url}/graphql",
            json={"query": "{ company { name } }"},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {customer_token}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        gql_b2b = resp.json()
    except requests.RequestException as e:
        stages["B2B Module"] = ("FAIL", f"GraphQL endpoint error: {e}")
        print_summary(stages)
        sys.exit(1)

    if "errors" in gql_b2b:
        stages["B2B Module"] = ("FAIL", f"GraphQL B2B error: {gql_b2b['errors'][0]['message']}")
        print_summary(stages)
        sys.exit(1)

    company_name = gql_b2b.get("data", {}).get("company", {}).get("name", "unknown")
    print(f"  GraphQL B2B query: OK (company: {company_name})")
    stages["B2B Module"] = ("PASS", f"company: {company_name}")

    # =========================================================================
    # STAGE 4: Full GraphQL Extraction Query
    # =========================================================================
    print("\nStage 4/5: Full GraphQL Extraction Query")
    print("---")

    extraction_query = (
        "query VezaExtraction { customer { email firstname lastname } "
        "company { id name legal_name email company_admin { email firstname lastname } "
        "structure { items { id parent_id entity { __typename "
        "... on Customer { email firstname lastname job_title telephone status "
        "role { id name } team { id name structure_id } } "
        "... on CompanyTeam { id name description } } } } } }"
    )

    try:
        resp = requests.post(
            f"{magento_url}/graphql",
            json={"query": extraction_query},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {customer_token}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        gql_full = resp.json()
    except requests.RequestException as e:
        stages["GraphQL Extraction"] = ("FAIL", f"Full query failed: {e}")
        print_summary(stages)
        sys.exit(1)

    if "errors" in gql_full:
        stages["GraphQL Extraction"] = ("FAIL", f"GraphQL error: {gql_full['errors'][0]['message']}")
        print_summary(stages)
        sys.exit(1)

    items = gql_full.get("data", {}).get("company", {}).get("structure", {}).get("items", [])
    if not items:
        stages["GraphQL Extraction"] = ("FAIL", "structure.items is empty or missing")
        print_summary(stages)
        sys.exit(1)

    company_data = gql_full["data"]["company"]
    full_name = company_data.get("name", "unknown")
    legal_name = company_data.get("legal_name", "N/A")
    admin_email = company_data.get("company_admin", {}).get("email", "unknown")

    users = [i for i in items if i.get("entity", {}).get("__typename") == "Customer"]
    teams = [i for i in items if i.get("entity", {}).get("__typename") == "CompanyTeam"]
    role_names = sorted(set(
        u["entity"]["role"]["name"]
        for u in users
        if u.get("entity", {}).get("role", {}).get("name")
    ))

    print(f"  Company:     {full_name}")
    print(f"  Legal Name:  {legal_name}")
    print(f"  Admin:       {admin_email}")
    print(f"  Users:       {len(users)}")
    print(f"  Teams:       {len(teams)}")
    print(f"  Roles:       {len(role_names)} ({', '.join(role_names)})")

    stages["GraphQL Extraction"] = ("PASS", f"{len(users)} users, {len(teams)} teams, {len(role_names)} roles")

    # =========================================================================
    # STAGE 5: REST Role Permissions
    # =========================================================================
    print("\nStage 5/5: REST Role Permissions")
    print("---")

    try:
        resp = requests.get(
            f"{magento_url}/rest/V1/company/role",
            params={"searchCriteria[pageSize]": 100},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        role_data = resp.json()
    except requests.RequestException:
        stages["REST Permissions"] = ("WARN", "REST role endpoint unreachable (non-blocking)")
        print("  Warning: Could not fetch role permissions (non-blocking)")
        print_summary(stages)
        sys.exit(0)

    if isinstance(role_data, dict) and "message" in role_data:
        stages["REST Permissions"] = ("WARN", "REST role endpoint returned error (non-blocking)")
        print("  Warning: Role endpoint error (non-blocking)")
        print_summary(stages)
        sys.exit(0)

    rest_roles = role_data.get("items", [])
    max_acl = 0

    for role in rest_roles:
        allow_count = sum(1 for p in role.get("permissions", []) if p.get("permission") == "allow")
        max_acl = max(max_acl, allow_count)
        print(f"  Role: {role.get('role_name', '?')} — {allow_count} permissions (allow)")

    print(f"\n  {len(rest_roles)} roles found, max {max_acl} ACL resources")
    stages["REST Permissions"] = ("PASS", f"{len(rest_roles)} roles, {max_acl} ACL resources")

    # =========================================================================
    # Summary
    # =========================================================================
    print_summary(stages)


if __name__ == "__main__":
    main()

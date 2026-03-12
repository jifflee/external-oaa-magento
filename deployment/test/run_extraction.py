#!/usr/bin/env python3
"""
run_extraction.py — Lightweight B2B data extraction (50 records per entity).

Pulls company structure, users, teams, roles, and permissions directly via
HTTP and saves each entity type as a separate JSON in a timestamped output
folder matching the project convention: YYYYMMDD_HHMMSS_{label}

Note on the 50-record limit:
  The GraphQL company.structure query has NO server-side pagination — Magento
  returns ALL structure items in one response. The 50-record cap is applied
  client-side after download. For companies with hundreds of users the full
  response is still fetched over the network; the limit only controls how many
  records are saved to disk. The REST /company/role endpoint does support
  server-side pageSize, so that limit is real.

Cross-platform: works on Windows, macOS, and Linux.
Prerequisites: Python 3.9+, requests (pip install requests)

Usage:
    # With env vars:
    MAGENTO_URL=https://magento.example.com \
    COMPANY_ADMIN_EMAIL=admin@company.com \
    COMPANY_ADMIN_PASSWORD=secret \
    MAGENTO_ADMIN_USER=admin \
    MAGENTO_ADMIN_PASS=secret \
    python run_extraction.py

    # Interactive (prompts for missing values):
    python run_extraction.py
"""

import base64
import json
import os
import sys
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is required. Install with: pip install requests")
    sys.exit(1)


PAGE_SIZE = 50

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class Colors:
    """ANSI colors — disabled on Windows without colorama or non-tty."""
    ENABLED = sys.stdout.isatty() and os.name != "nt"
    RED = "\033[0;31m" if ENABLED else ""
    GREEN = "\033[0;32m" if ENABLED else ""
    YELLOW = "\033[0;33m" if ENABLED else ""
    NC = "\033[0m" if ENABLED else ""


def prompt_if_missing(env_var: str, prompt_text: str, secret: bool = False) -> str:
    """Read from env var or prompt interactively."""
    value = os.environ.get(env_var, "").strip()
    if value:
        return value
    if secret:
        return getpass(f"{prompt_text}: ")
    return input(f"{prompt_text}: ").strip()


def save_json(path: Path, data) -> int:
    """Write data as formatted JSON. Returns file size in bytes."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path.stat().st_size


def fmt_size(n: int) -> str:
    """Format bytes as human-readable size."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def fatal(msg: str):
    print(f"{Colors.RED}ERROR: {msg}{Colors.NC}")
    sys.exit(1)


def warn(msg: str):
    print(f"{Colors.YELLOW}WARNING: {msg}{Colors.NC}")


def get_token(session: requests.Session, url: str, username: str, password: str, label: str) -> str:
    """Authenticate and return a JWT token string."""
    try:
        resp = session.post(url, json={"username": username, "password": password}, timeout=15)
        resp.raise_for_status()
        token = resp.json()
    except requests.exceptions.SSLError:
        fatal(f"{label}: TLS/certificate error. Self-signed cert? Try http:// or verify CA.")
    except requests.RequestException as e:
        fatal(f"{label}: Request failed — {e}")

    if isinstance(token, dict) and "message" in token:
        fatal(f"{label}: {token['message']}")
    if not isinstance(token, str) or len(token) < 10:
        fatal(f"{label}: Unexpected token format")

    return token


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # -- Collect credentials --------------------------------------------------
    magento_url = prompt_if_missing(
        "MAGENTO_URL", "Magento base URL (e.g. https://magento.example.com)"
    ).rstrip("/")
    company_email = prompt_if_missing("COMPANY_ADMIN_EMAIL", "Company admin email")
    company_pass = prompt_if_missing("COMPANY_ADMIN_PASSWORD", "Company admin password", secret=True)
    admin_user = prompt_if_missing("MAGENTO_ADMIN_USER", "Magento admin username")
    admin_pass = prompt_if_missing("MAGENTO_ADMIN_PASS", "Magento admin password", secret=True)

    # -- Create output directory (YYYYMMDD_HHMMSS to avoid collisions) --------
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = Path(__file__).resolve().parent
    output_dir = script_dir / "output" / f"{timestamp}_B2B_Extraction"
    output_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 40)
    print(f"B2B DATA EXTRACTION (limit: {PAGE_SIZE} per entity)")
    print("=" * 40)
    print(f"  Target:  {magento_url}")
    print(f"  Output:  {output_dir}")
    print()

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # =========================================================================
    # Step 1: Authenticate
    # =========================================================================
    print("Step 1/5: Authenticating")
    print("---")

    customer_token = get_token(
        session,
        f"{magento_url}/rest/V1/integration/customer/token",
        company_email, company_pass,
        "Customer auth",
    )
    print("  Customer token: OK")

    admin_token = get_token(
        session,
        f"{magento_url}/rest/V1/integration/admin/token",
        admin_user, admin_pass,
        "Admin auth",
    )
    print("  Admin token:    OK")

    # =========================================================================
    # Step 2: Extract company + structure via GraphQL
    # =========================================================================
    print("\nStep 2/5: Extracting company structure (GraphQL)")
    print("---")

    extraction_query = (
        "query VezaExtraction { customer { email firstname lastname } "
        "company { id name legal_name email company_admin { email firstname lastname } "
        "legal_address { street city region { region_code } postcode country_code telephone } "
        "structure { items { id parent_id entity { __typename "
        "... on Customer { email firstname lastname job_title telephone status created_at "
        "role { id name } team { id name structure_id } } "
        "... on CompanyTeam { id name description } } } } } }"
    )

    try:
        resp = session.post(
            f"{magento_url}/graphql",
            json={"query": extraction_query},
            headers={"Authorization": f"Bearer {customer_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        gql = resp.json()
    except requests.RequestException as e:
        fatal(f"GraphQL extraction failed: {e}")

    if "errors" in gql:
        fatal(f"GraphQL error: {gql['errors'][0]['message']}")

    company_data = gql.get("data", {}).get("company", {})
    if not company_data:
        fatal("No company data in GraphQL response")

    items = company_data.get("structure", {}).get("items", [])
    if not items:
        fatal("structure.items is empty or missing")

    # -- company.json ---------------------------------------------------------
    company_out = {
        "id": company_data.get("id"),
        "name": company_data.get("name"),
        "legal_name": company_data.get("legal_name"),
        "email": company_data.get("email"),
        "company_admin": company_data.get("company_admin"),
        "legal_address": company_data.get("legal_address"),
    }
    save_json(output_dir / "company.json", company_out)
    company_name = company_out["name"] or "unknown"
    company_id_raw = company_out["id"]
    print(f"  company.json — {company_name}")

    # Split items into users and teams
    all_users = []
    all_teams = []
    for item in items:
        entity = item.get("entity", {})
        typename = entity.get("__typename", "")
        if typename == "Customer":
            all_users.append({
                "structure_id": item.get("id"),
                "parent_id": item.get("parent_id"),
                "email": entity.get("email"),
                "firstname": entity.get("firstname"),
                "lastname": entity.get("lastname"),
                "job_title": entity.get("job_title"),
                "telephone": entity.get("telephone"),
                "status": entity.get("status"),
                "created_at": entity.get("created_at"),
                "role_id": (entity.get("role") or {}).get("id"),
                "role_name": (entity.get("role") or {}).get("name"),
                "team_id": (entity.get("team") or {}).get("id"),
                "team_name": (entity.get("team") or {}).get("name"),
            })
        elif typename == "CompanyTeam":
            all_teams.append({
                "structure_id": item.get("id"),
                "parent_id": item.get("parent_id"),
                "id": entity.get("id"),
                "name": entity.get("name"),
                "description": entity.get("description"),
            })

    total_users = len(all_users)
    total_teams = len(all_teams)
    total_items = len(items)

    # -- users.json (capped at PAGE_SIZE) -------------------------------------
    users_out = all_users[:PAGE_SIZE]
    save_json(output_dir / "users.json", users_out)
    trunc_note = f" (truncated from {total_users})" if total_users > PAGE_SIZE else ""
    print(f"  users.json — {len(users_out)} users{trunc_note}")

    # -- teams.json (capped at PAGE_SIZE) -------------------------------------
    teams_out = all_teams[:PAGE_SIZE]
    save_json(output_dir / "teams.json", teams_out)
    trunc_note = f" (truncated from {total_teams})" if total_teams > PAGE_SIZE else ""
    print(f"  teams.json — {len(teams_out)} teams{trunc_note}")

    # -- structure.json (FULL — not truncated for hierarchy integrity) ---------
    structure_out = [
        {"id": item.get("id"), "parent_id": item.get("parent_id"), "type": item.get("entity", {}).get("__typename")}
        for item in items
    ]
    save_json(output_dir / "structure.json", structure_out)
    print(f"  structure.json — {len(structure_out)} nodes (full hierarchy, not truncated)")

    # =========================================================================
    # Step 3: Extract roles via REST (with permissions)
    # =========================================================================
    print("\nStep 3/5: Extracting roles via REST")
    print("---")

    # Decode base64 company ID for REST filter
    company_id_numeric = None
    if company_id_raw:
        try:
            decoded = base64.b64decode(str(company_id_raw)).decode("utf-8")
            if decoded.isdigit():
                company_id_numeric = decoded
        except Exception:
            pass

    rest_params = {"searchCriteria[pageSize]": PAGE_SIZE}
    if company_id_numeric:
        rest_params.update({
            "searchCriteria[filter_groups][0][filters][0][field]": "company_id",
            "searchCriteria[filter_groups][0][filters][0][value]": company_id_numeric,
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
        })
    else:
        print("  Note: Could not decode company_id — fetching all roles")

    roles_list = []
    try:
        resp = session.get(
            f"{magento_url}/rest/V1/company/role",
            params=rest_params,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        roles_data = resp.json()

        if isinstance(roles_data, dict) and "message" in roles_data:
            warn(f"REST role error: {roles_data['message']} — skipping")
        else:
            roles_list = roles_data.get("items", [])
    except requests.RequestException as e:
        warn(f"REST /company/role failed ({e}) — skipping")

    save_json(output_dir / "roles.json", roles_list)
    role_count = len(roles_list)
    print(f"  roles.json — {role_count} roles")

    # =========================================================================
    # Step 4: Extract permissions per role
    # =========================================================================
    print("\nStep 4/5: Extracting role permissions")
    print("---")

    if role_count > 0:
        permissions_out = []
        for role in roles_list:
            perms = role.get("permissions", [])
            permissions_out.append({
                "role_id": role.get("id"),
                "role_name": role.get("role_name"),
                "company_id": role.get("company_id"),
                "permissions_allow": [p["resource_id"] for p in perms if p.get("permission") == "allow"],
                "permissions_deny": [p["resource_id"] for p in perms if p.get("permission") == "deny"],
            })
        save_json(output_dir / "permissions.json", permissions_out)
        total_allow = sum(len(p["permissions_allow"]) for p in permissions_out)
        print(f"  permissions.json — {role_count} roles, {total_allow} total allow entries")
    else:
        save_json(output_dir / "permissions.json", [])
        print("  permissions.json — skipped (no roles)")

    # =========================================================================
    # Step 5: Save extraction metadata
    # =========================================================================
    print("\nStep 5/5: Saving metadata")
    print("---")

    metadata = {
        "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "store_url": magento_url,
        "company": company_name,
        "record_limit": PAGE_SIZE,
        "counts": {
            "users": len(users_out),
            "teams": len(teams_out),
            "roles": role_count,
            "structure": len(structure_out),
        },
        "totals_before_truncation": {
            "users": total_users,
            "teams": total_teams,
            "all_items": total_items,
        },
        "notes": (
            "GraphQL company.structure has no server-side pagination. All items "
            "are fetched; users/teams are truncated client-side to record_limit. "
            "Structure is kept complete for hierarchy integrity."
        ),
        "files": [
            "company.json", "users.json", "teams.json", "structure.json",
            "roles.json", "permissions.json", "extraction_metadata.json",
        ],
    }
    save_json(output_dir / "extraction_metadata.json", metadata)
    print("  extraction_metadata.json — OK")

    # =========================================================================
    # Summary
    # =========================================================================
    print()
    print("=" * 40)
    print(f"{Colors.GREEN}Extraction complete.{Colors.NC}")
    print("=" * 40)
    print(f"  Output:  {output_dir}/")
    print()
    print("  Files:")
    for f in sorted(output_dir.glob("*.json")):
        print(f"    {f.name}  ({fmt_size(f.stat().st_size)})")
    print()
    print("  Counts:")
    print(f"    Company:      {company_name}")
    print(f"    Users:        {len(users_out)}/{total_users} (limit {PAGE_SIZE})")
    print(f"    Teams:        {len(teams_out)}/{total_teams} (limit {PAGE_SIZE})")
    print(f"    Roles:        {role_count} (limit {PAGE_SIZE})")
    print(f"    Structure:    {len(structure_out)} (full — not truncated)")
    print("=" * 40)


if __name__ == "__main__":
    main()

"""
Entity Extractor — Parses the raw GraphQL response into normalized domain entities.

This module sits between the raw API response (Step 2) and the OAA application
builder (Step 5). It takes the nested GraphQL JSON and produces a flat,
normalized dict of entities that downstream modules can consume without
knowing anything about the GraphQL response shape.

The GraphQL response has this structure:
    {
      "customer": { "email": "...", "firstname": "...", "lastname": "..." },
      "company": {
        "id": "MQ==",           # base64-encoded company ID
        "name": "Acme Corp",
        "structure": {
          "items": [            # flat list of all entities in the company tree
            {
              "id": "1",        # structure_id (position in the tree)
              "parent_id": "0", # parent's structure_id
              "entity": {
                "__typename": "Customer" | "CompanyTeam",
                ...entity-specific fields...
              }
            }
          ]
        }
      }
    }

Output format (returned by extract()):
    {
      "company": { "id", "name", "legal_name", "email", "admin_email", ... },
      "users": [ { "email", "firstname", "lastname", "role_id", "team_id", ... } ],
      "teams": [ { "id", "name", "description", "company_id", ... } ],
      "roles": [ { "id", "name", "company_id", ... } ],
      "hierarchy": [ { "child_type", "child_entity", "parent_type", "parent_entity" } ],
      "admin_email": "admin@example.com"
    }

Key behaviors:
  - Magento GraphQL IDs are base64-encoded (e.g., "MQ==" = "1"). decode_graphql_id()
    decodes them to plain numeric strings.
  - Roles are deduplicated by role_id (multiple users may share the same role).
  - Hierarchy is resolved from structure_id parent/child links to actual entity
    references, enabling reports_to relationships.

Pipeline context:
    Used in Step 4 of the orchestrator pipeline. Input comes from
    MagentoGraphQLClient.execute_graphql() (Step 2). Output feeds into
    ApplicationBuilder.build() (Step 5) and RelationshipBuilder.build_all() (Step 6).
"""

import base64
from typing import Dict, List, Any, Optional


def decode_graphql_id(encoded_id: str) -> str:
    """Decode a Magento GraphQL base64 ID to its numeric string value.

    Magento encodes entity IDs as base64 in GraphQL responses.
    Example: "MQ==" -> "1", "Mg==" -> "2", "Ng==" -> "6"

    Args:
        encoded_id: The base64-encoded ID string from GraphQL.

    Returns:
        The decoded numeric string, or the original value if decoding fails.
    """
    try:
        return base64.b64decode(encoded_id).decode("utf-8")
    except Exception:
        return encoded_id


class EntityExtractor:
    """Extracts and normalizes entities from the raw GraphQL response.

    Walks the company.structure.items array, separating Customer and
    CompanyTeam entities, deduplicating roles, and resolving the
    parent/child hierarchy into entity-level relationships.

    Attributes:
        debug: If True, prints extraction counts.
    """

    def __init__(self, debug: bool = False):
        self.debug = debug

    def extract(self, graphql_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all entities from the GraphQL response.

        Args:
            graphql_data: The "data" portion of the GraphQL response, expected
                          to contain "customer" and "company" keys.

        Returns:
            A dict with keys: company, users, teams, roles, hierarchy, admin_email.
            See module docstring for the full schema.
        """
        company_data = graphql_data.get("company", {})
        structure_items = company_data.get("structure", {}).get("items", [])

        # Extract top-level company info
        company = self._extract_company(company_data)

        # The company admin email is used to flag the admin user
        admin_email = company_data.get("company_admin", {}).get("email", "")

        # Walk the structure items to extract users, teams, roles, and hierarchy
        users = []
        teams = []
        roles = {}  # role_id -> role_info (deduplicated across users)
        hierarchy = []  # list of {child_structure_id, parent_structure_id}

        # Maps structure_id -> entity info for hierarchy resolution
        structure_map = {}

        for item in structure_items:
            structure_id = item.get("id", "")
            parent_id = item.get("parent_id", "")
            entity = item.get("entity", {})
            entity_type = entity.get("__typename", "")

            if entity_type == "Customer":
                user = self._extract_user(entity, company.get("id", ""), admin_email)
                users.append(user)
                structure_map[structure_id] = {"type": "Customer", "entity": user}

                # Deduplicate roles by role_id
                role_data = entity.get("role")
                if role_data and role_data.get("id"):
                    role_id = decode_graphql_id(role_data["id"])
                    if role_id not in roles:
                        roles[role_id] = {
                            "id": role_id,
                            "name": role_data.get("name", ""),
                            "company_id": company.get("id", ""),
                            "graphql_id": role_data["id"],
                        }

            elif entity_type == "CompanyTeam":
                team = self._extract_team(entity, company.get("id", ""))
                teams.append(team)
                structure_map[structure_id] = {"type": "CompanyTeam", "entity": team}

            # Record hierarchy link for later resolution
            if parent_id:
                hierarchy.append({
                    "child_structure_id": structure_id,
                    "parent_structure_id": parent_id,
                })

        # Resolve structure-based hierarchy to actual entity relationships
        resolved_hierarchy = self._resolve_hierarchy(hierarchy, structure_map)

        result = {
            "company": company,
            "users": users,
            "teams": teams,
            "roles": list(roles.values()),
            "hierarchy": resolved_hierarchy,
            "admin_email": admin_email,
        }

        if self.debug:
            print(f"  Extracted: {len(users)} users, {len(teams)} teams, "
                  f"{len(roles)} roles")

        return result

    def _extract_company(self, company_data: Dict) -> Dict:
        """Extract company info from the top-level company object.

        Args:
            company_data: The "company" portion of the GraphQL response.

        Returns:
            A normalized dict with id, name, legal_name, email, admin_*, graphql_id.
        """
        company_id = decode_graphql_id(company_data.get("id", ""))
        admin = company_data.get("company_admin", {})
        return {
            "id": company_id,
            "name": company_data.get("name", ""),
            "legal_name": company_data.get("legal_name", ""),
            "email": company_data.get("email", ""),
            "admin_email": admin.get("email", ""),
            "admin_firstname": admin.get("firstname", ""),
            "admin_lastname": admin.get("lastname", ""),
            "graphql_id": company_data.get("id", ""),
        }

    def _extract_user(self, entity: Dict, company_id: str, admin_email: str) -> Dict:
        """Extract a user from a Customer entity in the structure tree.

        Args:
            entity: The Customer entity dict from structure.items[].entity.
            company_id: The decoded company ID this user belongs to.
            admin_email: The company admin's email (for is_company_admin flag).

        Returns:
            A normalized user dict with email, name, status, role, team, etc.
        """
        email = entity.get("email", "")
        status = entity.get("status", "")

        # Team assignment (may be None if user is not in a team)
        team_data = entity.get("team")
        team_id = None
        if team_data and team_data.get("id"):
            team_id = decode_graphql_id(team_data["id"])

        # Role assignment (may be None)
        role_data = entity.get("role")
        role_id = None
        role_name = None
        if role_data and role_data.get("id"):
            role_id = decode_graphql_id(role_data["id"])
            role_name = role_data.get("name", "")

        return {
            "email": email,
            "firstname": entity.get("firstname", ""),
            "lastname": entity.get("lastname", ""),
            "job_title": entity.get("job_title", ""),
            "telephone": entity.get("telephone", ""),
            "is_active": status == "ACTIVE" if status else True,
            "status_raw": status,
            "is_company_admin": email.lower() == admin_email.lower() if admin_email else False,
            "company_id": company_id,
            "team_id": team_id,
            "role_id": role_id,
            "role_name": role_name,
        }

    def _extract_team(self, entity: Dict, company_id: str) -> Dict:
        """Extract a team from a CompanyTeam entity in the structure tree.

        Args:
            entity: The CompanyTeam entity dict from structure.items[].entity.
            company_id: The decoded company ID this team belongs to.

        Returns:
            A normalized team dict with id, name, description, company_id, graphql_id.
        """
        team_id = decode_graphql_id(entity.get("id", ""))
        return {
            "id": team_id,
            "name": entity.get("name", ""),
            "description": entity.get("description", ""),
            "company_id": company_id,
            "graphql_id": entity.get("id", ""),
        }

    def _resolve_hierarchy(self, hierarchy: List[Dict], structure_map: Dict) -> List[Dict]:
        """Resolve structure-ID-based hierarchy into entity-level relationships.

        The GraphQL response uses opaque structure_ids to express the company
        tree. This method maps those IDs back to the actual entities (users
        and teams) to produce relationships like "user A reports to user B".

        Args:
            hierarchy: List of {child_structure_id, parent_structure_id} dicts.
            structure_map: Maps structure_id -> {"type": ..., "entity": ...}.

        Returns:
            A list of resolved relationship dicts with child_type, child_entity,
            parent_type, and parent_entity keys.
        """
        resolved = []
        for link in hierarchy:
            child_id = link["child_structure_id"]
            parent_id = link["parent_structure_id"]

            child_info = structure_map.get(child_id)
            parent_info = structure_map.get(parent_id)

            if not child_info or not parent_info:
                continue

            resolved.append({
                "child_type": child_info["type"],
                "child_entity": child_info["entity"],
                "parent_type": parent_info["type"],
                "parent_entity": parent_info["entity"],
            })

        return resolved

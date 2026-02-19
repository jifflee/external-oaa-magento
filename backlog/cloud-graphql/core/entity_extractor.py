"""
Entity Extractor - Parses GraphQL response into domain entities.

Extracts: users, teams, roles, company from the GraphQL response
and normalizes the data for OAA transformation.
"""

import base64
from typing import Dict, List, Any, Optional, Tuple


def decode_graphql_id(encoded_id: str) -> str:
    """Decode a Magento GraphQL base64 ID to its numeric string value.

    Example: "MQ==" -> "1", "Mg==" -> "2", "Ng==" -> "6"
    """
    try:
        return base64.b64decode(encoded_id).decode("utf-8")
    except Exception:
        return encoded_id


class EntityExtractor:
    """Extracts and normalizes entities from GraphQL response."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def extract(self, graphql_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all entities from GraphQL response.

        Args:
            graphql_data: The 'data' portion of GraphQL response containing
                         'customer' and 'company' keys.

        Returns:
            Dict with keys: company, users, teams, roles, hierarchy, admin_email
        """
        company_data = graphql_data.get("company", {})
        customer_data = graphql_data.get("customer", {})
        structure_items = company_data.get("structure", {}).get("items", [])

        # Extract company info
        company = self._extract_company(company_data)

        # Extract admin email
        admin_email = company_data.get("company_admin", {}).get("email", "")

        # Extract entities from structure
        users = []
        teams = []
        roles = {}  # role_id -> role_info (deduplicated)
        hierarchy = []  # list of {child_structure_id, parent_structure_id}

        # Build structure_id -> entity mapping for hierarchy resolution
        structure_map = {}  # structure_id -> {"type": "Customer"|"CompanyTeam", "entity": {...}}

        for item in structure_items:
            structure_id = item.get("id", "")
            parent_id = item.get("parent_id", "")
            entity = item.get("entity", {})
            entity_type = entity.get("__typename", "")

            if entity_type == "Customer":
                user = self._extract_user(entity, company.get("id", ""), admin_email)
                users.append(user)
                structure_map[structure_id] = {"type": "Customer", "entity": user}

                # Extract role (deduplicated by role_id)
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

            # Record hierarchy link
            if parent_id:
                hierarchy.append({
                    "child_structure_id": structure_id,
                    "parent_structure_id": parent_id,
                })

        # Resolve hierarchy to actual entity relationships
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
        """Extract company info."""
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
        """Extract user from Customer entity."""
        email = entity.get("email", "")
        status = entity.get("status", "")

        # Team info
        team_data = entity.get("team")
        team_id = None
        if team_data and team_data.get("id"):
            team_id = decode_graphql_id(team_data["id"])

        # Role info
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
        """Extract team from CompanyTeam entity."""
        team_id = decode_graphql_id(entity.get("id", ""))
        return {
            "id": team_id,
            "name": entity.get("name", ""),
            "description": entity.get("description", ""),
            "company_id": company_id,
            "graphql_id": entity.get("id", ""),
        }

    def _resolve_hierarchy(self, hierarchy: List[Dict], structure_map: Dict) -> List[Dict]:
        """Resolve structure-based hierarchy into entity relationships.

        Produces reports_to relationships between users.
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

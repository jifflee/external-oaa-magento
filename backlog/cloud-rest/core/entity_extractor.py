"""
Entity Extractor - Parses REST API responses into domain entities.

Handles the differences from GraphQL:
- Status is numeric (1=active, 0=inactive) instead of ACTIVE/INACTIVE
- Hierarchy is a nested tree, not flat items
- Team details require separate API calls
- User-role link is NOT available (handled by role_gap_handler)
"""

from typing import Dict, List, Any, Optional


class EntityExtractor:
    """Extracts and normalizes entities from REST API responses."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def extract(
        self,
        current_user: Dict,
        company: Dict,
        roles: List[Dict],
        hierarchy: Dict,
        team_details: Dict[int, Dict],
    ) -> Dict[str, Any]:
        """Extract all entities from REST API responses.

        Args:
            current_user: Response from GET /V1/customers/me
            company: Response from GET /V1/company/{id}
            roles: Response from GET /V1/company/role (items array)
            hierarchy: Response from GET /V1/hierarchy/{companyId}
            team_details: Dict of team_id -> team detail from GET /V1/team/{id}

        Returns:
            Dict with keys: company, users, teams, roles, hierarchy, admin_email
        """
        company_id = str(company.get("id", ""))
        super_user_id = company.get("super_user_id")

        # Extract company info
        company_entity = self._extract_company(company)

        # Flatten hierarchy tree to get all users and teams
        flat_nodes = []
        self._flatten_hierarchy(hierarchy, flat_nodes)

        # Extract users from hierarchy nodes
        users = []
        for node in flat_nodes:
            if node.get("entity_type") == "customer":
                user = self._extract_user_from_hierarchy(
                    node, company_id, super_user_id, current_user
                )
                if user:
                    users.append(user)

        # If the authenticated user is not in the hierarchy, add them
        auth_email = current_user.get("email", "")
        if auth_email and not any(u["email"] == auth_email for u in users):
            user = self._extract_user_from_customer(current_user, company_id, super_user_id)
            users.append(user)

        # Extract teams
        teams = []
        team_ids_seen = set()
        for node in flat_nodes:
            if node.get("entity_type") == "team":
                tid = node.get("entity_id")
                if tid and tid not in team_ids_seen:
                    team_ids_seen.add(tid)
                    detail = team_details.get(tid, {})
                    team = self._extract_team(node, detail, company_id)
                    teams.append(team)

        # Extract roles (already have full data from REST)
        role_entities = []
        for role in roles:
            role_entities.append({
                "id": str(role.get("id", "")),
                "name": role.get("role_name", ""),
                "company_id": company_id,
                "permissions": role.get("permissions", []),
            })

        # Build hierarchy links
        hierarchy_links = self._extract_hierarchy_links(flat_nodes)

        # Derive admin email
        admin_email = ""
        if super_user_id:
            for user in users:
                if user.get("magento_customer_id") == str(super_user_id):
                    admin_email = user["email"]
                    break

        result = {
            "company": company_entity,
            "users": users,
            "teams": teams,
            "roles": role_entities,
            "hierarchy": hierarchy_links,
            "admin_email": admin_email,
        }

        if self.debug:
            print(f"  Extracted: {len(users)} users, {len(teams)} teams, {len(role_entities)} roles")

        return result

    def _extract_company(self, company: Dict) -> Dict:
        """Extract company entity from REST response."""
        return {
            "id": str(company.get("id", "")),
            "name": company.get("company_name", ""),
            "legal_name": company.get("legal_name", ""),
            "email": company.get("company_email", ""),
            "super_user_id": company.get("super_user_id"),
            "admin_email": "",  # Will be derived later
        }

    def _extract_user_from_customer(self, customer: Dict, company_id: str, super_user_id: Any) -> Dict:
        """Extract user from GET /V1/customers/me response."""
        email = customer.get("email", "")
        customer_id = customer.get("id")
        company_attrs = customer.get("extension_attributes", {}).get("company_attributes", {})

        return {
            "email": email,
            "firstname": customer.get("firstname", ""),
            "lastname": customer.get("lastname", ""),
            "job_title": company_attrs.get("job_title", ""),
            "telephone": company_attrs.get("telephone", ""),
            "is_active": company_attrs.get("status") == 1,
            "is_company_admin": customer_id == super_user_id if super_user_id else False,
            "company_id": company_id,
            "team_id": None,  # Not available from customers/me
            "role_id": None,  # NOT available in REST API (critical gap)
            "role_name": None,
            "magento_customer_id": str(customer_id) if customer_id else "",
        }

    def _extract_user_from_hierarchy(
        self, node: Dict, company_id: str, super_user_id: Any, current_user: Dict
    ) -> Optional[Dict]:
        """Extract user from a hierarchy node.

        Hierarchy nodes only contain entity_id (customer ID).
        We can only get full details for the authenticated user.
        For other users, we create minimal entries.
        """
        entity_id = node.get("entity_id")
        if not entity_id:
            return None

        # Check if this is the authenticated user
        if current_user.get("id") == entity_id:
            user = self._extract_user_from_customer(current_user, company_id, super_user_id)
            # Add hierarchy context
            user["_structure_id"] = node.get("structure_id")
            user["_parent_structure_id"] = node.get("structure_parent_id")
            return user

        # For other users, create minimal entry (REST limitation)
        return {
            "email": f"customer_{entity_id}@unknown",
            "firstname": "",
            "lastname": "",
            "job_title": "",
            "telephone": "",
            "is_active": True,  # Unknown, assume active
            "is_company_admin": entity_id == super_user_id if super_user_id else False,
            "company_id": company_id,
            "team_id": None,
            "role_id": None,
            "role_name": None,
            "magento_customer_id": str(entity_id),
            "_structure_id": node.get("structure_id"),
            "_parent_structure_id": node.get("structure_parent_id"),
        }

    def _extract_team(self, node: Dict, detail: Dict, company_id: str) -> Dict:
        """Extract team from hierarchy node + detail response."""
        team_id = node.get("entity_id")
        return {
            "id": str(team_id) if team_id else "",
            "name": detail.get("name", f"Team {team_id}"),
            "description": detail.get("description", ""),
            "company_id": company_id,
            "_structure_id": node.get("structure_id"),
        }

    def _flatten_hierarchy(self, node: Dict, result: List[Dict]):
        """Recursively flatten hierarchy tree into flat list of nodes."""
        if not node:
            return

        result.append({
            "structure_id": node.get("structure_id"),
            "entity_id": node.get("entity_id"),
            "entity_type": node.get("entity_type", "").lower(),
            "structure_parent_id": node.get("structure_parent_id"),
        })

        for child in node.get("children", []):
            self._flatten_hierarchy(child, result)

    def _extract_hierarchy_links(self, flat_nodes: List[Dict]) -> List[Dict]:
        """Build hierarchy links for reports_to relationships."""
        # Build structure_id -> node map
        structure_map = {}
        for node in flat_nodes:
            sid = node.get("structure_id")
            if sid:
                structure_map[sid] = node

        links = []
        for node in flat_nodes:
            parent_sid = node.get("structure_parent_id")
            if parent_sid and parent_sid in structure_map:
                parent = structure_map[parent_sid]
                links.append({
                    "child_type": "Customer" if node["entity_type"] == "customer" else "CompanyTeam",
                    "child_entity": node,
                    "parent_type": "Customer" if parent["entity_type"] == "customer" else "CompanyTeam",
                    "parent_entity": parent,
                })

        return links

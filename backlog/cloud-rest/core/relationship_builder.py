"""
Relationship Builder - Wires up all OAA relationships for Commerce Cloud REST connector.

Same 6 relationship types as GraphQL connector.
User->Role may be absent depending on role_gap_handler strategy.
"""

from typing import Dict, List, Any, Optional
from oaaclient.templates import CustomApplication

from magento_oaa_shared.permissions import MAGENTO_ACL_PERMISSIONS


class RelationshipBuilder:
    """Builds all OAA relationships from REST-extracted entities."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def build_all(self, app: CustomApplication, entities: Dict[str, Any]):
        """Build all 6 relationship types."""
        company = entities["company"]
        users = entities["users"]
        teams = entities["teams"]
        roles = entities["roles"]
        hierarchy = entities.get("hierarchy", [])

        company_uid = f"company_{company['id']}"

        # 1. User -> Company
        for user in users:
            local_user = app.local_users.get(user["email"])
            if local_user:
                try:
                    local_user.add_group(company_uid)
                except Exception:
                    pass

        # 2. User -> Team (from hierarchy: user's parent is a team)
        self._build_user_team_from_hierarchy(app, hierarchy, users)

        # 3. User -> Role (may be None if gap handler chose skip/all_roles)
        for user in users:
            if user.get("role_id"):
                role_uid = f"role_{company['id']}_{user['role_id']}"
                local_user = app.local_users.get(user["email"])
                if local_user and role_uid in app.local_roles:
                    try:
                        local_user.add_role(role=role_uid, apply_to_application=True)
                    except Exception:
                        pass

        # 4. Role -> Permission (from REST data with explicit allow/deny)
        for role in roles:
            role_uid = f"role_{company['id']}_{role['id']}"
            local_role = app.local_roles.get(role_uid)
            if not local_role:
                continue

            for perm in role.get("permissions", []):
                resource_id = perm.get("resource_id", "")
                if perm.get("permission") == "allow" and resource_id in MAGENTO_ACL_PERMISSIONS:
                    try:
                        local_role.add_permissions([resource_id])
                    except Exception:
                        pass

        # 5. Team -> Company
        company_group = app.local_groups.get(company_uid)
        if company_group:
            for team in teams:
                team_uid = f"team_{team['id']}"
                if team_uid in app.local_groups:
                    try:
                        company_group.add_group(team_uid)
                    except Exception:
                        pass

        # 6. User -> User reports_to
        self._build_reports_to(app, hierarchy)

        if self.debug:
            print(f"  Relationships built")

    def _build_user_team_from_hierarchy(self, app, hierarchy, users):
        """Build user->team from hierarchy (user's parent is a team)."""
        for link in hierarchy:
            if link["child_type"] == "Customer" and link["parent_type"] == "CompanyTeam":
                child_entity = link["child_entity"]
                parent_entity = link["parent_entity"]
                customer_id = str(child_entity.get("entity_id", ""))
                team_id = str(parent_entity.get("entity_id", ""))

                # Find user by customer_id
                for user in users:
                    if user.get("magento_customer_id") == customer_id:
                        team_uid = f"team_{team_id}"
                        local_user = app.local_users.get(user["email"])
                        if local_user and team_uid in app.local_groups:
                            try:
                                local_user.add_group(team_uid)
                            except Exception:
                                pass
                        break

    def _build_reports_to(self, app, hierarchy):
        """Build user->user reports_to (customer parent is customer).

        This is limited in REST since we don't have emails for all users.
        Only works when we can resolve both entities to known local users.
        """
        # Limited by REST - hierarchy only has IDs, not emails.
        # Resolution would require a secondary email lookup not available
        # via REST for users other than the authenticated caller.
        pass

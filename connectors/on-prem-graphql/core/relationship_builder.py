"""
Relationship Builder - Wires up all OAA relationships.

6 relationship types:
1. User -> Company (member_of)
2. User -> Team (member_of)
3. User -> Role (assigned_role)
4. Role -> Permission (grants, only 'allow')
5. Team -> Company (parent_group)
6. User -> User (reports_to, from hierarchy)
"""

from typing import Dict, List, Any, Optional
from oaaclient.templates import CustomApplication

from magento_oaa_shared.permissions import MAGENTO_ACL_PERMISSIONS


class RelationshipBuilder:
    """Builds all OAA relationships from extracted entities."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def build_all(
        self,
        app: CustomApplication,
        entities: Dict[str, Any],
        rest_roles: Optional[List[Dict]] = None,
    ):
        """Build all 6 relationship types.

        Args:
            app: The CustomApplication to add relationships to
            entities: Output from EntityExtractor.extract()
            rest_roles: Optional REST role data with explicit permissions
        """
        company = entities["company"]
        users = entities["users"]
        teams = entities["teams"]
        roles = entities["roles"]
        hierarchy = entities["hierarchy"]

        company_unique_id = f"company_{company['id']}"

        # 1. User -> Company (all users belong to the company)
        self._build_user_company(app, users, company_unique_id)

        # 2. User -> Team
        self._build_user_team(app, users)

        # 3. User -> Role
        self._build_user_role(app, users, company["id"])

        # 4. Role -> Permission (from REST supplement or GraphQL permissions tree)
        self._build_role_permissions(app, roles, company["id"], rest_roles)

        # 5. Team -> Company
        self._build_team_company(app, teams, company_unique_id)

        # 6. User -> User (reports_to from hierarchy)
        self._build_reports_to(app, hierarchy)

        if self.debug:
            print(f"  Relationships built for {len(users)} users, {len(teams)} teams, {len(roles)} roles")

    def _build_user_company(self, app: CustomApplication, users: List[Dict], company_unique_id: str):
        """Relationship 1: User -> Company membership."""
        for user in users:
            try:
                local_user = app.local_users.get(user["email"])
                if local_user:
                    local_user.add_group(company_unique_id)
            except Exception as e:
                if self.debug:
                    print(f"    Warning: Could not add user {user['email']} to company: {e}")

    def _build_user_team(self, app: CustomApplication, users: List[Dict]):
        """Relationship 2: User -> Team membership."""
        for user in users:
            if user.get("team_id"):
                team_unique_id = f"team_{user['team_id']}"
                try:
                    local_user = app.local_users.get(user["email"])
                    if local_user and team_unique_id in app.local_groups:
                        local_user.add_group(team_unique_id)
                except Exception as e:
                    if self.debug:
                        print(f"    Warning: Could not add user {user['email']} to team: {e}")

    def _build_user_role(self, app: CustomApplication, users: List[Dict], company_id: str):
        """Relationship 3: User -> Role assignment."""
        for user in users:
            if user.get("role_id"):
                role_unique_id = f"role_{company_id}_{user['role_id']}"
                try:
                    local_user = app.local_users.get(user["email"])
                    if local_user and role_unique_id in app.local_roles:
                        local_user.add_role(role=role_unique_id, apply_to_application=True)
                except Exception as e:
                    if self.debug:
                        print(f"    Warning: Could not assign role to {user['email']}: {e}")

    def _build_role_permissions(
        self,
        app: CustomApplication,
        roles: List[Dict],
        company_id: str,
        rest_roles: Optional[List[Dict]] = None,
    ):
        """Relationship 4: Role -> Permission grants.

        If rest_roles provided (from REST supplement), use explicit allow/deny.
        Otherwise, grant all known permissions to each role.
        """
        if rest_roles:
            # Use REST data: explicit allow/deny per role
            self._build_role_permissions_from_rest(app, rest_roles, company_id)
        else:
            # Without REST supplement, we don't have explicit permission data.
            # GraphQL role only gives id+name, not permissions list.
            # In this case, we create roles but can't link permissions.
            if self.debug:
                print("    No REST role supplement - role->permission links unavailable")

    def _build_role_permissions_from_rest(
        self,
        app: CustomApplication,
        rest_roles: List[Dict],
        company_id: str,
    ):
        """Build role->permission from REST role data with explicit allow/deny."""
        for rest_role in rest_roles:
            role_id = str(rest_role.get("id", ""))
            role_unique_id = f"role_{company_id}_{role_id}"

            local_role = app.local_roles.get(role_unique_id)
            if not local_role:
                continue

            permissions = rest_role.get("permissions", [])
            allowed_count = 0

            for perm in permissions:
                resource_id = perm.get("resource_id", "")
                permission_value = perm.get("permission", "")

                # Only create links for "allow" permissions
                if permission_value == "allow" and resource_id in MAGENTO_ACL_PERMISSIONS:
                    try:
                        local_role.add_permissions([resource_id])
                        allowed_count += 1
                    except Exception as e:
                        if self.debug:
                            print(f"    Warning: Could not add permission {resource_id} to role: {e}")

            if self.debug:
                print(f"    Role {rest_role.get('role_name', role_id)}: {allowed_count} permissions")

    def _build_team_company(self, app: CustomApplication, teams: List[Dict], company_unique_id: str):
        """Relationship 5: Team -> Company parent group."""
        company_group = app.local_groups.get(company_unique_id)
        if not company_group:
            return

        for team in teams:
            team_unique_id = f"team_{team['id']}"
            try:
                team_group = app.local_groups.get(team_unique_id)
                if team_group:
                    # In OAA, groups can nest. Add team as sub-group of company.
                    company_group.add_group(team_unique_id)
            except Exception as e:
                if self.debug:
                    print(f"    Warning: Could not add team {team['id']} to company: {e}")

    def _build_reports_to(self, app: CustomApplication, hierarchy: List[Dict]):
        """Relationship 6: User -> User reports_to from hierarchy.

        Only creates reports_to when both child and parent are Customer entities.
        """
        for link in hierarchy:
            if link["child_type"] == "Customer" and link["parent_type"] == "Customer":
                child_email = link["child_entity"].get("email", "")
                parent_email = link["parent_entity"].get("email", "")

                if child_email and parent_email and child_email != parent_email:
                    try:
                        child_user = app.local_users.get(child_email)
                        parent_user = app.local_users.get(parent_email)
                        if child_user and parent_user:
                            child_user.set_property("reports_to", parent_email)
                    except Exception as e:
                        if self.debug:
                            print(f"    Warning: Could not set reports_to for {child_email}: {e}")

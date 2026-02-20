"""
Relationship Builder — Wires all 6 OAA relationship types between entities.

After the ApplicationBuilder (Step 5) creates the OAA users, groups, and roles,
this module connects them with the proper relationship links. These relationships
are what make the extracted data meaningful for authorization analysis.

The 6 relationship types:

  1. User -> Company (group membership)
     Every user is a member of their company group. This is always set.

  2. User -> Team (group membership)
     If a user belongs to a team, they are added to that team's group.

  3. User -> Role (role assignment)
     If a user has a B2B role, they are assigned to it. The role assignment
     is applied at the application level (apply_to_application=True).

  4. Role -> Permission (permission grants)
     If REST role supplement data is available, each role gets linked to its
     allowed ACL permissions. Only "allow" entries are included; "deny" entries
     are skipped. Without REST data, roles exist but have no permission links.

  5. Team -> Company (group nesting)
     Teams are nested as sub-groups under the company group, reflecting the
     organizational hierarchy.

  6. User -> User (reports_to)
     If the company structure shows a Customer reporting to another Customer,
     a reports_to property is set on the subordinate user. This only applies
     to Customer-to-Customer links (not team-to-user or user-to-team).

Pipeline context:
    Used in Step 6 of the orchestrator pipeline. Takes the CustomApplication
    from ApplicationBuilder (Step 5), the entities dict from EntityExtractor
    (Step 4), and optionally the REST role data from MagentoGraphQLClient (Step 3).
"""

from typing import Dict, List, Any, Optional
from oaaclient.templates import CustomApplication

from magento_oaa_shared.permissions import MAGENTO_ACL_PERMISSIONS


class RelationshipBuilder:
    """Builds all OAA relationships from extracted entities.

    Attributes:
        debug: If True, prints verbose details about relationship construction.
    """

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
            app: The CustomApplication populated by ApplicationBuilder.
            entities: Output from EntityExtractor.extract().
            rest_roles: Optional REST role data with explicit permission trees.
                        If None, role→permission links are skipped.
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

        # 4. Role -> Permission (from REST supplement or unavailable)
        self._build_role_permissions(app, roles, company["id"], rest_roles)

        # 5. Team -> Company
        self._build_team_company(app, teams, company_unique_id)

        # 6. User -> User (reports_to from hierarchy)
        self._build_reports_to(app, hierarchy)

        if self.debug:
            print(f"  Relationships built for {len(users)} users, {len(teams)} teams, {len(roles)} roles")

    def _build_user_company(self, app: CustomApplication, users: List[Dict], company_unique_id: str):
        """Relationship 1: Add every user to the company group.

        Args:
            app: The OAA CustomApplication.
            users: List of normalized user dicts.
            company_unique_id: The unique_id of the company group (e.g., "company_1").
        """
        for user in users:
            try:
                local_user = app.local_users.get(user["email"])
                if local_user:
                    local_user.add_group(company_unique_id)
            except Exception as e:
                if self.debug:
                    print(f"    Warning: Could not add user {user['email']} to company: {e}")

    def _build_user_team(self, app: CustomApplication, users: List[Dict]):
        """Relationship 2: Add users to their team group (if assigned).

        Args:
            app: The OAA CustomApplication.
            users: List of normalized user dicts (team_id may be None).
        """
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
        """Relationship 3: Assign users to their B2B role.

        The role unique_id follows the format "role_{company_id}_{role_id}".

        Args:
            app: The OAA CustomApplication.
            users: List of normalized user dicts (role_id may be None).
            company_id: The decoded company ID (used in role unique_id).
        """
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
        """Relationship 4: Link roles to their allowed ACL permissions.

        If rest_roles is provided (from the REST supplement in Step 3), each
        role is linked to its explicitly allowed permissions. If not available,
        roles exist in the OAA model but have no permission links.

        Args:
            app: The OAA CustomApplication.
            roles: List of normalized role dicts from EntityExtractor.
            company_id: The decoded company ID.
            rest_roles: Optional list of REST role dicts with permission arrays.
        """
        if rest_roles:
            self._build_role_permissions_from_rest(app, rest_roles, company_id)
        else:
            if self.debug:
                print("    No REST role supplement - role->permission links unavailable")

    def _build_role_permissions_from_rest(
        self,
        app: CustomApplication,
        rest_roles: List[Dict],
        company_id: str,
    ):
        """Build role->permission links from REST data with explicit allow/deny.

        Only "allow" permissions are linked. "deny" entries are skipped.
        Only known Magento ACL resource IDs (from the 34-entry catalog) are
        included; unknown resource IDs are ignored.

        Args:
            app: The OAA CustomApplication.
            rest_roles: List of REST role dicts from MagentoGraphQLClient.
            company_id: The decoded company ID.
        """
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

                # Only link "allow" permissions for known ACL resources
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
        """Relationship 5: Nest team groups under the company group.

        In the OAA model, groups can contain sub-groups. Each team is added
        as a child of the company group.

        Args:
            app: The OAA CustomApplication.
            teams: List of normalized team dicts.
            company_unique_id: The unique_id of the company group.
        """
        company_group = app.local_groups.get(company_unique_id)
        if not company_group:
            return

        for team in teams:
            team_unique_id = f"team_{team['id']}"
            try:
                team_group = app.local_groups.get(team_unique_id)
                if team_group:
                    company_group.add_group(team_unique_id)
            except Exception as e:
                if self.debug:
                    print(f"    Warning: Could not add team {team['id']} to company: {e}")

    def _build_reports_to(self, app: CustomApplication, hierarchy: List[Dict]):
        """Relationship 6: Set reports_to property for user→user hierarchy.

        Only creates reports_to when both the child and parent are Customer
        entities (not CompanyTeam). This reflects the actual reporting
        structure within the B2B company.

        Args:
            app: The OAA CustomApplication.
            hierarchy: Resolved hierarchy from EntityExtractor (list of
                       {child_type, child_entity, parent_type, parent_entity}).
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

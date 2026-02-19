"""
Application Builder - Constructs OAA CustomApplication from extracted entities.

Maps Magento B2B entities to Veza OAA model:
- Customer -> LocalUser
- Company -> LocalGroup (type=company)
- Team -> LocalGroup (type=team)
- Role -> LocalRole
- ACL Permission -> CustomPermission
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from oaaclient.templates import CustomApplication, OAAPropertyType

from config.permissions import define_oaa_permissions


class ApplicationBuilder:
    """Builds OAA CustomApplication from extracted Magento entities."""

    def __init__(self, store_url: str = "", debug: bool = False):
        self.store_url = store_url
        self.debug = debug

    def build(self, entities: Dict[str, Any]) -> CustomApplication:
        """Build complete OAA CustomApplication.

        Args:
            entities: Output from EntityExtractor.extract() containing
                     company, users, teams, roles, hierarchy, admin_email

        Returns:
            Fully populated CustomApplication ready for push
        """
        company = entities["company"]
        users = entities["users"]
        teams = entities["teams"]
        roles = entities["roles"]
        admin_email = entities.get("admin_email", "")

        app_name = f"magento_b2b_graphql_{company['id']}"

        app = CustomApplication(
            name=app_name,
            application_type="Magento B2B (GraphQL)",
            description=f"Adobe Commerce B2B - {company['name']} (GraphQL connector)",
        )

        # Define custom property types
        self._define_properties(app)

        # Set application-level properties
        app.set_property("store_url", self.store_url)
        app.set_property("sync_timestamp", datetime.now(timezone.utc).isoformat())
        app.set_property("company_name", company["name"])

        # Define permissions (33 ACL resources)
        define_oaa_permissions(app)

        # Add company as local group
        self._add_company_group(app, company)

        # Add teams as local groups
        for team in teams:
            self._add_team_group(app, team)

        # Add roles
        for role in roles:
            self._add_role(app, role)

        # Add users
        for user in users:
            self._add_user(app, user)

        if self.debug:
            print(f"  Built application: {app_name}")
            print(f"    Users: {len(app.local_users)}")
            print(f"    Groups: {len(app.local_groups)}")
            print(f"    Roles: {len(app.local_roles)}")

        return app

    def _define_properties(self, app: CustomApplication):
        """Define custom property schemas."""
        # Application properties
        app.property_definitions.define_application_property("store_url", OAAPropertyType.STRING)
        app.property_definitions.define_application_property("sync_timestamp", OAAPropertyType.STRING)
        app.property_definitions.define_application_property("company_name", OAAPropertyType.STRING)

        # User properties
        app.property_definitions.define_local_user_property("job_title", OAAPropertyType.STRING)
        app.property_definitions.define_local_user_property("telephone", OAAPropertyType.STRING)
        app.property_definitions.define_local_user_property("is_company_admin", OAAPropertyType.BOOLEAN)
        app.property_definitions.define_local_user_property("magento_customer_id", OAAPropertyType.STRING)
        app.property_definitions.define_local_user_property("company_id", OAAPropertyType.STRING)
        app.property_definitions.define_local_user_property("reports_to", OAAPropertyType.STRING)

        # Group properties (for both company and team types)
        app.property_definitions.define_local_group_property("legal_name", OAAPropertyType.STRING)
        app.property_definitions.define_local_group_property("company_email", OAAPropertyType.STRING)
        app.property_definitions.define_local_group_property("admin_email", OAAPropertyType.STRING)
        app.property_definitions.define_local_group_property("magento_company_id", OAAPropertyType.STRING)
        app.property_definitions.define_local_group_property("description", OAAPropertyType.STRING)
        app.property_definitions.define_local_group_property("magento_team_id", OAAPropertyType.STRING)
        app.property_definitions.define_local_group_property("parent_company_id", OAAPropertyType.STRING)

        # Role properties
        app.property_definitions.define_local_role_property("magento_role_id", OAAPropertyType.STRING)
        app.property_definitions.define_local_role_property("company_id", OAAPropertyType.STRING)

    def _add_company_group(self, app: CustomApplication, company: Dict):
        """Add company as LocalGroup."""
        unique_id = f"company_{company['id']}"
        group = app.add_local_group(
            name=company["name"],
            unique_id=unique_id,
            group_type="company",
        )
        group.set_property("legal_name", company.get("legal_name", ""))
        group.set_property("company_email", company.get("email", ""))
        group.set_property("admin_email", company.get("admin_email", ""))
        group.set_property("magento_company_id", company["id"])

    def _add_team_group(self, app: CustomApplication, team: Dict):
        """Add team as LocalGroup."""
        unique_id = f"team_{team['id']}"
        group = app.add_local_group(
            name=team["name"],
            unique_id=unique_id,
            group_type="team",
        )
        group.set_property("description", team.get("description", ""))
        group.set_property("magento_team_id", team["id"])
        group.set_property("parent_company_id", team.get("company_id", ""))

    def _add_role(self, app: CustomApplication, role: Dict):
        """Add role as LocalRole."""
        unique_id = f"role_{role['company_id']}_{role['id']}"
        local_role = app.add_local_role(
            name=role["name"],
            unique_id=unique_id,
        )
        local_role.set_property("magento_role_id", role["id"])
        local_role.set_property("company_id", role["company_id"])

    def _add_user(self, app: CustomApplication, user: Dict):
        """Add user as LocalUser."""
        email = user["email"]
        local_user = app.add_local_user(
            name=email,
            unique_id=email,
        )
        local_user.email = email
        local_user.first_name = user.get("firstname", "")
        local_user.last_name = user.get("lastname", "")
        local_user.is_active = user.get("is_active", True)
        local_user.add_identity(email)

        # Custom properties
        if user.get("job_title"):
            local_user.set_property("job_title", user["job_title"])
        if user.get("telephone"):
            local_user.set_property("telephone", user["telephone"])
        local_user.set_property("is_company_admin", user.get("is_company_admin", False))
        local_user.set_property("company_id", user.get("company_id", ""))

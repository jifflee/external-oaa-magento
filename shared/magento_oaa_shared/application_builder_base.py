"""
Base Application Builder — Shared OAA CustomApplication construction logic.

This module provides the BaseApplicationBuilder class, which creates and
populates a Veza OAA CustomApplication from the normalized entities dict
produced by EntityExtractor. It handles:

  1. Property schema definitions (application, user, group, role properties)
  2. Company group creation (type="company")
  3. Team group creation (type="team")
  4. Role creation with Magento role ID metadata
  5. User creation with identity, properties, and active/inactive status
  6. Registering all 34 Magento ACL permissions

The GraphQL connector subclasses this with ApplicationBuilder, which only
provides the connector-specific naming constants (app_name_prefix, application_type).

OAA property schemas defined:
  Application: store_url, sync_timestamp, company_name
  User:        job_title, telephone, is_company_admin, magento_customer_id,
               company_id, reports_to
  Group:       legal_name, company_email, admin_email, magento_company_id,
               description, magento_team_id, parent_company_id
  Role:        magento_role_id, company_id

Pipeline context:
    Used in Step 5 of the orchestrator pipeline. Input is the entities dict
    from EntityExtractor (Step 4). Output is a CustomApplication that
    RelationshipBuilder (Step 6) then wires with relationships.
"""

from typing import Dict, Any
from datetime import datetime, timezone

from oaaclient.templates import CustomApplication, OAAPropertyType

from .permissions import define_oaa_permissions


class BaseApplicationBuilder:
    """Builds an OAA CustomApplication from extracted Magento B2B entities.

    Subclasses provide connector-specific naming (app_name_prefix, application_type).
    This base class handles all entity-to-OAA mapping logic.

    Attributes:
        store_url: Base URL of the Magento store.
        app_name_prefix: Prefix for the OAA application name (e.g., "magento_onprem_graphql").
        application_type: OAA application type string.
        description_suffix: Appended to the OAA app description.
        debug: If True, prints verbose build details.
    """

    def __init__(
        self,
        store_url: str,
        app_name_prefix: str,
        application_type: str,
        description_suffix: str = "",
        debug: bool = False,
    ):
        self.store_url = store_url
        self.app_name_prefix = app_name_prefix
        self.application_type = application_type
        self.description_suffix = description_suffix
        self.debug = debug

    def build(self, entities: Dict[str, Any]) -> CustomApplication:
        """Build a complete OAA CustomApplication from extracted entities.

        Creates the application, defines property schemas, registers the 34
        ACL permissions, then adds the company group, teams, roles, and users.

        Args:
            entities: Output from EntityExtractor.extract() with keys:
                      company, users, teams, roles.

        Returns:
            A fully populated CustomApplication (without relationships —
            those are added by RelationshipBuilder in Step 6).
        """
        company = entities["company"]
        users = entities["users"]
        teams = entities["teams"]
        roles = entities["roles"]

        # Application name includes company ID for uniqueness
        app_name = f"{self.app_name_prefix}_{company['id']}"

        app = CustomApplication(
            name=app_name,
            application_type=self.application_type,
            description=f"Adobe Commerce B2B - {company['name']} ({self.description_suffix})",
        )

        # Define all property schemas before setting any values
        self._define_properties(app)

        # Set application-level metadata
        app.set_property("store_url", self.store_url)
        app.set_property("sync_timestamp", datetime.now(timezone.utc).isoformat())
        app.set_property("company_name", company["name"])

        # Register the 34 Magento B2B ACL permissions
        define_oaa_permissions(app)

        # Add entities
        self._add_company_group(app, company)

        for team in teams:
            self._add_team_group(app, team)

        for role in roles:
            self._add_role(app, role)

        for user in users:
            self._add_user(app, user)

        if self.debug:
            print(f"  Built application: {app_name}")
            print(f"    Users: {len(app.local_users)}")
            print(f"    Groups: {len(app.local_groups)}")
            print(f"    Roles: {len(app.local_roles)}")

        return app

    def _define_properties(self, app: CustomApplication):
        """Define custom property schemas on the OAA application.

        These must be defined before any set_property() calls. Defines schemas
        for application, user, group, and role property types.

        Args:
            app: The CustomApplication to define properties on.
        """
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

        # Group properties (used by both company and team groups)
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
        """Add the company as a local group with type="company".

        Args:
            app: The OAA CustomApplication.
            company: Normalized company dict from EntityExtractor.
        """
        unique_id = f"company_{company['id']}"
        group = app.add_local_group(name=company["name"], unique_id=unique_id)
        group.group_type = "company"
        group.set_property("legal_name", company.get("legal_name", ""))
        group.set_property("company_email", company.get("email", ""))
        group.set_property("admin_email", company.get("admin_email", ""))
        group.set_property("magento_company_id", company["id"])

    def _add_team_group(self, app: CustomApplication, team: Dict):
        """Add a team as a local group with type="team".

        Args:
            app: The OAA CustomApplication.
            team: Normalized team dict from EntityExtractor.
        """
        unique_id = f"team_{team['id']}"
        group = app.add_local_group(name=team["name"], unique_id=unique_id)
        group.group_type = "team"
        group.set_property("description", team.get("description", ""))
        group.set_property("magento_team_id", team["id"])
        group.set_property("parent_company_id", team.get("company_id", ""))

    def _add_role(self, app: CustomApplication, role: Dict):
        """Add a B2B role as a local role.

        The unique_id format is "role_{company_id}_{role_id}" to ensure
        uniqueness across companies.

        Args:
            app: The OAA CustomApplication.
            role: Normalized role dict from EntityExtractor.
        """
        unique_id = f"role_{role['company_id']}_{role['id']}"
        local_role = app.add_local_role(name=role["name"], unique_id=unique_id)
        local_role.set_property("magento_role_id", role["id"])
        local_role.set_property("company_id", role["company_id"])

    def _add_user(self, app: CustomApplication, user: Dict):
        """Add a company user as a local user with identity and properties.

        The user's email is used as both the name and unique_id. An identity
        is also added (for Veza identity resolution).

        Args:
            app: The OAA CustomApplication.
            user: Normalized user dict from EntityExtractor.
        """
        email = user["email"]
        local_user = app.add_local_user(name=email, unique_id=email)
        local_user.email = email
        local_user.first_name = user.get("firstname", "")
        local_user.last_name = user.get("lastname", "")
        local_user.is_active = user.get("is_active", True)
        local_user.add_identity(email)

        if user.get("job_title"):
            local_user.set_property("job_title", user["job_title"])
        if user.get("telephone"):
            local_user.set_property("telephone", user["telephone"])
        local_user.set_property("is_company_admin", user.get("is_company_admin", False))
        local_user.set_property("company_id", user.get("company_id", ""))
        if user.get("magento_customer_id"):
            local_user.set_property("magento_customer_id", user["magento_customer_id"])

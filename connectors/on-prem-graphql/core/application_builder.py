"""
Application Builder — Connector-specific subclass of BaseApplicationBuilder.

This thin subclass exists to provide the naming constants that distinguish the
on-prem GraphQL connector from other potential connectors. All of the actual
entity-mapping logic (creating users, groups, roles, property definitions)
lives in magento_oaa_shared.BaseApplicationBuilder.

What this subclass configures:
  - app_name_prefix: "magento_onprem_graphql" (used in the OAA app name)
  - application_type: "Magento B2B On-Prem (GraphQL)" (OAA metadata)
  - description_suffix: "On-Prem, GraphQL connector" (appended to app description)

Pipeline context:
    Used in Step 5 of the orchestrator pipeline. Takes the normalized entities
    dict from EntityExtractor (Step 4) and produces a fully populated
    OAA CustomApplication object that RelationshipBuilder (Step 6) then wires.
"""

from magento_oaa_shared.application_builder_base import BaseApplicationBuilder


class ApplicationBuilder(BaseApplicationBuilder):
    """OAA application builder for the Magento On-Prem GraphQL connector.

    Inherits all build logic from BaseApplicationBuilder. Only overrides
    the constructor to set connector-specific naming.
    """

    def __init__(self, store_url: str = "", debug: bool = False):
        """Initialize with on-prem GraphQL naming constants.

        Args:
            store_url: Base URL of the Magento store (stored as app property).
            debug: Enable verbose output during build.
        """
        super().__init__(
            store_url=store_url,
            app_name_prefix="magento_onprem_graphql",
            application_type="Magento B2B On-Prem (GraphQL)",
            description_suffix="On-Prem, GraphQL connector",
            debug=debug,
        )

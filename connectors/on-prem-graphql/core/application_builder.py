"""
Application Builder - Thin subclass of BaseApplicationBuilder for the
Magento On-Prem GraphQL connector.

All entity-mapping logic lives in magento_oaa_shared.BaseApplicationBuilder.
This subclass only provides the connector-specific naming constants.
"""

from magento_oaa_shared.application_builder_base import BaseApplicationBuilder


class ApplicationBuilder(BaseApplicationBuilder):
    """OAA application builder for the Magento On-Prem GraphQL connector."""

    def __init__(self, store_url: str = "", debug: bool = False):
        super().__init__(
            store_url=store_url,
            app_name_prefix="magento_onprem_graphql",
            application_type="Magento B2B On-Prem (GraphQL)",
            description_suffix="On-Prem, GraphQL connector",
            debug=debug,
        )

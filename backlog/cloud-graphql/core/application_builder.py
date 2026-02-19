"""
Application Builder - Thin subclass of BaseApplicationBuilder for Commerce Cloud GraphQL connector.

Uses shared base class for all OAA CustomApplication construction logic.
"""

from magento_oaa_shared.application_builder_base import BaseApplicationBuilder


class ApplicationBuilder(BaseApplicationBuilder):
    def __init__(self, store_url: str = "", debug: bool = False):
        super().__init__(
            store_url=store_url,
            app_name_prefix="commerce_cloud_graphql",
            application_type="Magento B2B Commerce Cloud (GraphQL)",
            description_suffix="Commerce Cloud, GraphQL connector",
            debug=debug,
        )

"""
Application Builder - OAA CustomApplication construction for Commerce Cloud REST connector.

Thin subclass of BaseApplicationBuilder with Commerce Cloud REST-specific naming.
"""

from magento_oaa_shared.application_builder_base import BaseApplicationBuilder


class ApplicationBuilder(BaseApplicationBuilder):
    def __init__(self, store_url: str = "", debug: bool = False):
        super().__init__(
            store_url=store_url,
            app_name_prefix="commerce_cloud_rest",
            application_type="Magento B2B Commerce Cloud (REST)",
            description_suffix="Commerce Cloud, REST connector",
            debug=debug,
        )

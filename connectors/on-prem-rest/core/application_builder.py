"""
Application Builder - Thin subclass of BaseApplicationBuilder for the
Magento On-Prem REST connector.

Provider:   Magento_OnPrem_REST
App name:   magento_onprem_rest_{company_id}
App type:   Magento B2B On-Prem (REST)
Description: Adobe Commerce B2B - {company_name} (On-Prem, REST connector)
"""

from magento_oaa_shared.application_builder_base import BaseApplicationBuilder


class ApplicationBuilder(BaseApplicationBuilder):
    """OAA application builder for the On-Prem REST connector."""

    def __init__(self, store_url: str = "", debug: bool = False):
        super().__init__(
            store_url=store_url,
            app_name_prefix="magento_onprem_rest",
            application_type="Magento B2B On-Prem (REST)",
            description_suffix="On-Prem, REST connector",
            debug=debug,
        )

"""
Settings and defaults for the Magento On-Prem GraphQL connector.
"""

PROVIDER_NAME = "Magento_OnPrem_GraphQL"

DEFAULT_SETTINGS = {
    "PROVIDER_NAME": PROVIDER_NAME,
    "PROVIDER_PREFIX": "",
    "OUTPUT_DIR": "./output",
    "OUTPUT_RETENTION_DAYS": 30,
    "DRY_RUN": True,
    "SAVE_JSON": True,
    "DEBUG": False,
    "USE_REST_ROLE_SUPPLEMENT": True,
}

PROXY_ENV_VARS = [
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "NO_PROXY", "no_proxy",
]

DEFAULT_SETTINGS = {
    "PROVIDER_NAME": "Commerce_Cloud_REST",
    "PROVIDER_PREFIX": "",
    "OUTPUT_DIR": "./output",
    "OUTPUT_RETENTION_DAYS": 30,
    "DRY_RUN": True,
    "SAVE_JSON": True,
    "DEBUG": False,
    "USER_ROLE_STRATEGY": "default_role",
    "USER_ROLE_MAPPING_PATH": "./data/user_role_mapping.csv",
}

PROXY_ENV_VARS = [
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "NO_PROXY", "no_proxy",
]

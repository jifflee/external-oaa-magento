"""
Settings — Default configuration values for the Magento On-Prem GraphQL connector.

This module provides the DEFAULT_SETTINGS dict that the orchestrator uses as
fallback values when environment variables are not set. The actual configuration
is loaded from .env at runtime; these defaults ensure the connector works out of
the box for common use cases.

Configuration precedence (highest to lowest):
  1. CLI flags (--debug, --no-rest)
  2. Environment variables (from .env file)
  3. DEFAULT_SETTINGS (this file)

Settings reference:
  PROVIDER_NAME           Label used in output folder naming (e.g., "Magento_OnPrem_GraphQL")
  OUTPUT_DIR              Where to write extraction output (default: ./output)
  OUTPUT_RETENTION_DAYS   How many days to keep old output folders (0 = keep forever)
  SAVE_JSON               Whether to write the OAA payload to disk (default: True)
  DEBUG                   Whether to print verbose output (default: False)
  USE_REST_ROLE_SUPPLEMENT Whether to call the REST role endpoint for per-role permissions
"""

PROVIDER_NAME = "Magento_OnPrem_GraphQL"

DEFAULT_SETTINGS = {
    "PROVIDER_NAME": PROVIDER_NAME,
    "OUTPUT_DIR": "./output",
    "OUTPUT_RETENTION_DAYS": 30,
    "SAVE_JSON": True,
    "DEBUG": False,
    "USE_REST_ROLE_SUPPLEMENT": True,
}

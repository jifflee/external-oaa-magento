"""
================================================================================
SETTINGS - Customer Configuration
================================================================================

PURPOSE:
    Central location for customer-specific settings and configurations.
    Modify this file to customize the connector for your organization.

CUSTOMIZATION:
    1. Add permission names to KNOWN_PERMISSIONS as you classify them
    2. Update DEFAULT_SETTINGS to change default behavior

================================================================================
"""

# ==============================================================================
# KNOWN PERMISSIONS
# ==============================================================================
#
# Permissions in this set are considered "classified" and will map to
# predefined roles. Any permission NOT in this set will:
#   - Be flagged as "NEEDS REVIEW" in the output
#   - Get a dynamically created role with "?" (Uncategorized) permission
#
# HOW TO ADD NEW PERMISSIONS:
#   1. Identify the permission name from your CSV data
#   2. Determine what effective permissions it should have (C, R, U, D, M, N)
#   3. Add the lowercase permission name to this set
#   4. Add the role mapping in roles.py (PERMISSION_TO_ROLE and ROLE_DEFINITIONS)
#
# EXAMPLE:
#   To add a new "DataAnalyst" permission that should have Read + Metadata:
#   1. Add "dataanalyst" to KNOWN_PERMISSIONS below
#   2. In roles.py, add to PERMISSION_TO_ROLE: "dataanalyst": "role_dataanalyst"
#   3. In roles.py, add to ROLE_DEFINITIONS: ("DataAnalyst", ["R", "M"], "role_dataanalyst")
#   4. In roles.py, add to ROLE_TO_EFFECTIVE: "dataanalyst": ["R", "M"]

KNOWN_PERMISSIONS = {
    # Standard roles
    "superadmin",   # Maps to SuperAdmin role [C,R,U,D,M,N]
    "admin",        # Maps to Admin role [C,R,U,D,M]
    "editor",       # Maps to Editor role [R,U]
    "readwrite",    # Maps to ReadWrite role [R,U]
    "contributor",  # Maps to Contributor role [C,R,U]
    "auditor",      # Maps to Auditor role [R,M]
    "readonly",     # Maps to ReadOnly role [R]

    # Aliases (alternative names that map to standard roles)
    "read",         # Alias for ReadOnly [R]
    "write",        # Alias for Editor [R,U]
    "viewer",       # Alias for ReadOnly [R]

    # ==========================================================================
    # ADD YOUR CUSTOM PERMISSIONS BELOW
    # ==========================================================================
    # Example:
    # "dataanalyst",    # Custom role for data analysts [R,M]
    # "reportviewer",   # Custom role for report viewers [R]
    # "systembackup",   # Custom role for backup operators [R,M]
}


# ==============================================================================
# DEFAULT SETTINGS
# ==============================================================================
#
# These defaults are used when environment variables are not set.
# Override any of these via .env file or environment variables.

DEFAULT_SETTINGS = {
    # Provider/Integration name (used in output folder naming)
    "PROVIDER_NAME": "Odie_Application",

    # Provider prefix for integration names (empty = no prefix)
    # If set, all integrations become: {PREFIX}_{App_Name}
    "PROVIDER_PREFIX": "",

    # Default CSV file in ./data/ folder
    "CSV_FILENAME": "sample_permissions.csv",

    # Output directory for JSON payloads
    "OUTPUT_DIR": "./output",

    # Days to keep output folders (0 = disable cleanup)
    "OUTPUT_RETENTION_DAYS": 30,

    # Processing options
    "DRY_RUN": True,      # True = generate JSON only, don't push to Veza
    "SAVE_JSON": True,    # True = save JSON payloads to disk
    "DEBUG": False,       # True = print stack traces on errors
}


# ==============================================================================
# PROXY CONFIGURATION
# ==============================================================================
# Set in .env if your network requires proxy to reach Veza cloud:
#   HTTP_PROXY=http://proxy.company.com:8080
#   HTTPS_PROXY=http://proxy.company.com:8080
#   NO_PROXY=localhost,127.0.0.1
#
# HOW IT WORKS:
#   1. load_dotenv() loads .env variables into os.environ
#   2. Python's requests library (used by oaaclient) automatically
#      reads HTTP_PROXY/HTTPS_PROXY from os.environ
#   3. All Veza API calls are routed through the proxy
#
# No code changes needed - proxy is handled automatically by requests library.

PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
]

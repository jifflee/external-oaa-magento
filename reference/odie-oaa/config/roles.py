"""
================================================================================
ROLES - Role Definitions and Permission Mappings
================================================================================

PURPOSE:
    Defines how permission names from CSV data map to roles, and what
    effective permissions each role grants. This is the PRIMARY file
    customers will modify to customize for their organization.

CUSTOMIZATION GUIDE:

    To add a new role (e.g., "DataAnalyst" with Read + Metadata access):

    1. Add to ROLE_DEFINITIONS:
       ("DataAnalyst", ["R", "M"], "role_dataanalyst"),

    2. Add to PERMISSION_TO_ROLE:
       "dataanalyst": "role_dataanalyst",

    3. Add to ROLE_TO_EFFECTIVE:
       "dataanalyst": ["R", "M"],

    4. Add to KNOWN_PERMISSIONS in settings.py:
       "dataanalyst",

DATA MODEL:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                         ROLE HIERARCHY                               │
    │                                                                      │
    │  CSV Permission Name ──► PERMISSION_TO_ROLE ──► Role ID             │
    │                                                                      │
    │  Role ID ──► ROLE_DEFINITIONS ──► Effective Permissions [C,R,U,D,M] │
    │                                                                      │
    │  Example:                                                            │
    │    CSV: "Admin" ──► PERMISSION_TO_ROLE["admin"] = "role_admin"      │
    │    "role_admin" ──► ROLE_DEFINITIONS["Admin"] = [C,R,U,D,M]         │
    └─────────────────────────────────────────────────────────────────────┘

================================================================================
"""

from typing import Tuple, List
from oaaclient.templates import CustomApplication


# ==============================================================================
# ROLE DEFINITIONS
# ==============================================================================
#
# Each tuple contains: (display_name, [effective_permissions], unique_id)
#
# - display_name: How the role appears in Veza UI
# - effective_permissions: List of base permission symbols (C, R, U, D, M, N)
# - unique_id: Internal identifier for the role (must be unique)
#
# ADD YOUR CUSTOM ROLES HERE

ROLE_DEFINITIONS = [
    # Standard roles
    ("SuperAdmin", ["C", "R", "U", "D", "M", "N"], "role_superadmin"),
    ("Admin", ["C", "R", "U", "D", "M"], "role_admin"),
    ("Editor", ["R", "U"], "role_editor"),
    ("ReadWrite", ["R", "U"], "role_readwrite"),
    ("Contributor", ["C", "R", "U"], "role_contributor"),
    ("Auditor", ["R", "M"], "role_auditor"),
    ("ReadOnly", ["R"], "role_readonly"),

    # ==========================================================================
    # ADD YOUR CUSTOM ROLES BELOW
    # ==========================================================================
    # Format: ("DisplayName", ["permissions"], "role_id")
    #
    # Example custom roles:
    # ("DataAnalyst", ["R", "M"], "role_dataanalyst"),
    # ("ReportViewer", ["R"], "role_reportviewer"),
    # ("SystemBackup", ["R", "M"], "role_systembackup"),
    # ("PowerUser", ["C", "R", "U", "M"], "role_poweruser"),
]


# ==============================================================================
# PERMISSION TO ROLE MAPPING
# ==============================================================================
#
# Maps CSV permission names (lowercase) to role IDs.
# When a permission name is found in CSV, this lookup determines which role
# the user gets assigned.
#
# ADD YOUR CUSTOM MAPPINGS HERE

PERMISSION_TO_ROLE = {
    # Standard mappings
    "superadmin": "role_superadmin",
    "admin": "role_admin",
    "editor": "role_editor",
    "readwrite": "role_readwrite",
    "contributor": "role_contributor",
    "auditor": "role_auditor",
    "readonly": "role_readonly",

    # Aliases (alternative names that map to standard roles)
    "read": "role_readonly",
    "write": "role_editor",
    "viewer": "role_readonly",

    # ==========================================================================
    # ADD YOUR CUSTOM MAPPINGS BELOW
    # ==========================================================================
    # Format: "csv_permission_name": "role_id"
    #
    # Example custom mappings:
    # "dataanalyst": "role_dataanalyst",
    # "reportviewer": "role_reportviewer",
    # "systembackup": "role_systembackup",
    # "poweruser": "role_poweruser",
    # "analyst": "role_dataanalyst",  # Alias
}


# ==============================================================================
# ROLE TO EFFECTIVE PERMISSIONS (for display)
# ==============================================================================
#
# Used for console output to show what permissions each role grants.
# Should mirror ROLE_DEFINITIONS but indexed by lowercase role name.

ROLE_TO_EFFECTIVE = {
    "superadmin": ["C", "R", "U", "D", "M", "N"],
    "admin": ["C", "R", "U", "D", "M"],
    "editor": ["R", "U"],
    "readwrite": ["R", "U"],
    "contributor": ["C", "R", "U"],
    "auditor": ["R", "M"],
    "readonly": ["R"],
    "needs_review": ["?"],

    # ==========================================================================
    # ADD YOUR CUSTOM ROLES BELOW (mirror ROLE_DEFINITIONS)
    # ==========================================================================
    # "dataanalyst": ["R", "M"],
    # "reportviewer": ["R"],
    # "systembackup": ["R", "M"],
    # "poweruser": ["C", "R", "U", "M"],
}


# ==============================================================================
# ROLE BUILDER FUNCTION
# ==============================================================================

def define_roles(app: CustomApplication, criticality: str = None, unclassified_roles: set = None) -> None:
    """
    Add role definitions to a CustomApplication.

    PURPOSE:
        Creates roles from ROLE_DEFINITIONS and any dynamically-discovered
        unclassified roles. Each role is assigned its effective permissions.

    ARGS:
        app: CustomApplication instance to add roles to
        criticality: Optional criticality value to tag roles with
        unclassified_roles: Set of role names not in ROLE_DEFINITIONS
                           (these get "?" permission)

    BEHAVIOR:
        1. Creates all roles from ROLE_DEFINITIONS
        2. If unclassified_roles provided, creates dynamic roles with "?" permission
        3. Optionally adds criticality tags/properties to all roles
    """
    # Create each defined role
    for role_name, permissions, role_id in ROLE_DEFINITIONS:
        role = app.add_local_role(role_name, permissions, unique_id=role_id)

        # Add criticality metadata if provided
        if criticality:
            role.add_tag("criticality", criticality)
            role.set_property("financial_criticality", criticality)

    # Create dynamic roles for unclassified permission names
    # These get "?" permission to flag them for governance review
    if unclassified_roles:
        for role_name in unclassified_roles:
            role_id = f"role_{role_name.lower().strip()}"
            role = app.add_local_role(role_name, ["?"], unique_id=role_id)

            if criticality:
                role.add_tag("criticality", criticality)
                role.set_property("financial_criticality", criticality)


# ==============================================================================
# PERMISSION MAPPING FUNCTION
# ==============================================================================

def map_permission_to_role(permission_name: str) -> Tuple[str, bool]:
    """
    Map a CSV permission name to a role ID.

    ARGS:
        permission_name: The permission value from CSV

    RETURNS:
        Tuple of (role_id, is_classified):
        - role_id: The internal role identifier
        - is_classified: True if in PERMISSION_TO_ROLE, False if dynamic

    E?AMPLE:
        map_permission_to_role("Admin")        # ("role_admin", True)
        map_permission_to_role("SpecialAccess") # ("role_specialaccess", False)
    """
    perm_lower = permission_name.lower().strip()

    if perm_lower in PERMISSION_TO_ROLE:
        return (PERMISSION_TO_ROLE[perm_lower], True)
    else:
        # Unknown role names get their own dynamically-created role
        role_id = f"role_{perm_lower}"
        return (role_id, False)


def get_role_effective_permissions(role_name: str) -> List[str]:
    """
    Get the effective permissions for a role (for display purposes).

    ARGS:
        role_name: The role name to look up

    RETURNS:
        List of permission symbols (e.g., ["C", "R", "U", "D", "M"])
        Returns ["?"] for unknown roles

    E?AMPLE:
        get_role_effective_permissions("Admin")    # ["C", "R", "U", "D", "M"]
        get_role_effective_permissions("Unknown")  # ["?"]
    """
    return ROLE_TO_EFFECTIVE.get(role_name.lower(), ["?"])

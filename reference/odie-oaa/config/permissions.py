"""
================================================================================
PERMISSIONS - Base Permission Definitions
================================================================================

PURPOSE:
    Defines the atomic (base) permissions that roles are built from.
    These map to Veza's canonical OAAPermission types.

PERMISSION MODEL:
    ┌─────────┬─────────────────────────────────┬────────────────────────┐
    │ Symbol  │ Veza OAAPermission              │ Meaning                │
    ├─────────┼─────────────────────────────────┼────────────────────────┤
    │ C       │ DataCreate                      │ Create new data        │
    │ R       │ DataRead                        │ Read/view data         │
    │ U       │ DataWrite                       │ Update/modify data     │
    │ D       │ DataDelete                      │ Delete data            │
    │ M       │ MetadataRead + MetadataWrite    │ Read/write metadata    │
    │ N       │ NonData                         │ Non-data operations    │
    │ ?       │ Uncategorized                   │ Unknown/needs review   │
    └─────────┴─────────────────────────────────┴────────────────────────┘

CUSTOMIZATION:
    Typically no changes needed. Only modify if your organization needs
    different base permission types beyond CRUD + Metadata.

================================================================================
"""

from oaaclient.templates import CustomApplication, OAAPermission


# ==============================================================================
# BASE PERMISSION DEFINITIONS
# ==============================================================================
#
# Each tuple contains: (symbol, [OAAPermission types], description)
# The symbol is what appears in role definitions (e.g., "C", "R", "U")

BASE_PERMISSIONS = [
    # Create - ability to create new records/data
    ("C", [OAAPermission.DataCreate], "Create new data"),

    # Read - ability to view/read existing data
    ("R", [OAAPermission.DataRead], "Read/view data"),

    # Update - ability to modify existing data
    ("U", [OAAPermission.DataWrite], "Update/modify data"),

    # Delete - ability to remove data
    ("D", [OAAPermission.DataDelete], "Delete data"),

    # Metadata - ability to read and write metadata (config, settings, etc.)
    ("M", [OAAPermission.MetadataRead, OAAPermission.MetadataWrite], "Read/write metadata"),

    # NonData - operations that don't involve data (admin functions, etc.)
    ("N", [OAAPermission.NonData], "Non-data operations"),

    # Uncategorized - placeholder for unknown permissions (needs governance review)
    ("?", [OAAPermission.Uncategorized], "Uncategorized - needs review"),
]


# ==============================================================================
# PERMISSION BUILDER FUNCTION
# ==============================================================================

def define_base_permissions(app: CustomApplication) -> None:
    """
    Add base permission definitions to a CustomApplication.

    PURPOSE:
        Creates the foundational permission types that roles will reference.
        These are atomic permissions that map to Veza's canonical permission
        types, enabling Veza to understand what each permission allows.

    ARGS:
        app: CustomApplication instance to add permissions to

    USAGE:
        app = CustomApplication(name="MyApp", application_type="MyApp")
        define_base_permissions(app)
        # Now app has C, R, U, D, M, N, ? permissions defined
    """
    for symbol, oaa_permissions, description in BASE_PERMISSIONS:
        app.add_custom_permission(symbol, oaa_permissions)

    # Special handling for "?" permission - add description for Veza UI
    # This makes uncategorized permissions easily identifiable
    if "?" in app.custom_permissions:
        perm = app.custom_permissions["?"]
        original_to_dict = perm.to_dict
        def to_dict_with_description():
            d = original_to_dict()
            d["description"] = "Uncategorized"
            return d
        perm.to_dict = to_dict_with_description

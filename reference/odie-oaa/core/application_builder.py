"""
================================================================================
APPLICATION BUILDER - OAA CustomApplication Construction (Core Module)
================================================================================

PURPOSE:
    Builds Veza OAA CustomApplication objects from CSV data.
    This is a CORE module - do not modify.

    Uses configuration from config/ package for:
    - Permission definitions (config.permissions)
    - Role definitions and mappings (config.roles)

================================================================================
"""

from typing import Dict, List, Tuple

from oaaclient.templates import CustomApplication, OAAPropertyType

# Import customer-configurable items from config package
from config import (
    define_base_permissions,
    define_roles,
    map_permission_to_role
)


def build_application(app_id: str, app_rows: List[Dict[str, str]]) -> Tuple[CustomApplication, set]:
    """
    Build a CustomApplication object from CSV rows for a single application.

    PROCESSING FLOW:
        1. Extract application metadata from first row
        2. Create CustomApplication with properties
        3. Identify unclassified roles (first pass through data)
        4. Define base permissions (C, R, U, D, M, N, ?)
        5. Define roles (known + dynamic for unclassified)
        6. Process users and assign roles

    ARGS:
        app_id: The Application_FIN_ID value
        app_rows: All CSV rows for this application

    RETURNS:
        Tuple of (CustomApplication, set of unclassified permission names)
    """
    # -------------------------------------------------------------------------
    # STEP 1: Extract application metadata
    # -------------------------------------------------------------------------
    first_row = app_rows[0]
    app_name = first_row.get('Application_FIN_Name', app_id)
    app_criticality = first_row.get('Application_FIN_Criticality', '')

    # Create the CustomApplication
    app = CustomApplication(
        name=app_name,
        application_type=app_name,
        description=f"Application ID: {app_id}"
    )

    # -------------------------------------------------------------------------
    # STEP 2: Define custom properties
    # -------------------------------------------------------------------------
    app.property_definitions.define_application_property("fin_id", OAAPropertyType.STRING)
    app.property_definitions.define_application_property("financial_criticality", OAAPropertyType.STRING)
    app.property_definitions.define_local_user_property("user_id", OAAPropertyType.STRING)
    app.property_definitions.define_local_role_property("financial_criticality", OAAPropertyType.STRING)

    # Set application properties
    app.set_property("fin_id", app_id)
    if app_criticality:
        app.set_property("financial_criticality", app_criticality)
        app.add_tag("criticality", app_criticality)

    # -------------------------------------------------------------------------
    # STEP 3: First pass - identify unclassified roles
    # -------------------------------------------------------------------------
    unclassified_roles = set()
    for row in app_rows:
        role_name = row.get('Permission', '').strip()
        if role_name:
            role_id, is_classified = map_permission_to_role(role_name)
            if not is_classified:
                unclassified_roles.add(role_name)

    # -------------------------------------------------------------------------
    # STEP 4: Define base permissions (uses config.permissions)
    # -------------------------------------------------------------------------
    define_base_permissions(app)

    # -------------------------------------------------------------------------
    # STEP 5: Define roles (uses config.roles)
    # -------------------------------------------------------------------------
    define_roles(app, criticality=app_criticality, unclassified_roles=unclassified_roles)

    # -------------------------------------------------------------------------
    # STEP 6: Process users and assign roles
    # -------------------------------------------------------------------------
    added_users = {}

    for row in app_rows:
        user_id = row.get('User Id', '').strip()
        user_name = row.get('User Name', '').strip()
        user_email = row.get('User Email', '').strip()
        permission = row.get('Permission', '').strip()

        if not user_id:
            continue

        # Add user if not already added
        if user_id not in added_users:
            user = app.add_local_user(
                name=user_name if user_name else user_id,
                unique_id=user_id
            )
            user.set_property("user_id", user_id)

            if user_email:
                user.email = user_email
                user.add_identity(user_email)

            user.is_active = True
            added_users[user_id] = user
        else:
            user = added_users[user_id]

        # Assign role to user
        if permission:
            role_id, _ = map_permission_to_role(permission)
            user.add_role(role=role_id, apply_to_application=True)

    return app, unclassified_roles

"""
Magento B2B ACL Permission Definitions.

34 granular ACL resources from Magento B2B.
These resource IDs are returned by both GraphQL and REST APIs.

Source: Adobe Commerce B2B documentation (b2b-roles.md)
"""

from oaaclient.templates import OAAPermission


# Complete ACL permission catalog - 34 resources
# Key = resource_id as returned by Magento API
# Value = (display_name, category)
MAGENTO_ACL_PERMISSIONS = {
    # Base
    "Magento_Company::index": ("All Access", "base"),

    # Sales
    "Magento_Sales::all": ("Sales", "sales"),
    "Magento_Sales::place_order": ("Allow Checkout", "sales"),
    "Magento_Sales::payment_account": ("Pay On Account", "sales"),
    "Magento_Sales::view_orders": ("View Orders", "sales"),
    "Magento_Sales::view_orders_sub": ("View Subordinate Orders", "sales"),

    # Quotes
    "Magento_NegotiableQuote::all": ("Quotes", "quotes"),
    "Magento_NegotiableQuote::view_quotes": ("View Quotes", "quotes"),
    "Magento_NegotiableQuote::manage": ("Manage Quotes", "quotes"),
    "Magento_NegotiableQuote::checkout": ("Checkout Quote", "quotes"),
    "Magento_NegotiableQuote::view_quotes_sub": ("View Subordinate Quotes", "quotes"),

    # Purchase Orders
    "Magento_PurchaseOrder::all": ("Order Approvals", "purchase_orders"),
    "Magento_PurchaseOrder::view_purchase_orders": ("View My POs", "purchase_orders"),
    "Magento_PurchaseOrder::view_purchase_orders_for_subordinates": ("View Subordinate POs", "purchase_orders"),
    "Magento_PurchaseOrder::view_purchase_orders_for_company": ("View Company POs", "purchase_orders"),
    "Magento_PurchaseOrder::autoapprove_purchase_order": ("Auto-approve POs", "purchase_orders"),
    # Note: These 3 use PurchaseOrderRule (not PurchaseOrder) per official Magento docs
    "Magento_PurchaseOrderRule::super_approve_purchase_order": ("Super Approve", "purchase_orders"),
    "Magento_PurchaseOrderRule::view_approval_rules": ("View Approval Rules", "purchase_orders"),
    "Magento_PurchaseOrderRule::manage_approval_rules": ("Manage Approval Rules", "purchase_orders"),

    # Company Profile
    "Magento_Company::view": ("Company Profile", "company"),
    "Magento_Company::view_account": ("View Account", "company"),
    "Magento_Company::edit_account": ("Edit Account", "company"),
    "Magento_Company::view_address": ("View Address", "company"),
    "Magento_Company::edit_address": ("Edit Address", "company"),
    "Magento_Company::contacts": ("View Contacts", "company"),
    "Magento_Company::payment_information": ("View Payment Info", "company"),
    "Magento_Company::shipping_information": ("View Shipping Info", "company"),

    # User Management
    "Magento_Company::user_management": ("User Management", "users"),
    "Magento_Company::roles_view": ("View Roles", "users"),
    "Magento_Company::roles_edit": ("Manage Roles", "users"),
    "Magento_Company::users_view": ("View Users", "users"),
    "Magento_Company::users_edit": ("Manage Users", "users"),

    # Credit
    "Magento_Company::credit": ("Company Credit", "credit"),
    "Magento_Company::credit_history": ("Credit History", "credit"),
}

# Categories with OAA permission type mapping
PERMISSION_CATEGORIES = {
    "base": "DataRead",
    "sales": "DataWrite",
    "quotes": "DataWrite",
    "purchase_orders": "DataWrite",
    "company": "DataRead",
    "users": "DataWrite",
    "credit": "DataRead",
}


def get_permission_name(resource_id: str) -> str:
    """Get display name for a resource ID."""
    entry = MAGENTO_ACL_PERMISSIONS.get(resource_id)
    return entry[0] if entry else resource_id


def get_permission_category(resource_id: str) -> str:
    """Get category for a resource ID."""
    entry = MAGENTO_ACL_PERMISSIONS.get(resource_id)
    return entry[1] if entry else "unknown"


def define_oaa_permissions(app):
    """Define all 34 Magento ACL permissions on a CustomApplication."""
    for resource_id, (display_name, category) in MAGENTO_ACL_PERMISSIONS.items():
        permissions = []
        perm_type = PERMISSION_CATEGORIES.get(category, "DataRead")
        if perm_type == "DataRead":
            permissions.append(OAAPermission.DataRead)
        elif perm_type == "DataWrite":
            permissions.append(OAAPermission.DataWrite)
        else:
            permissions.append(OAAPermission.DataRead)

        app.add_custom_permission(
            permission_name=resource_id,
            permissions=permissions
        )

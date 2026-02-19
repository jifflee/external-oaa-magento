"""Tests for magento_oaa_shared.permissions."""

import pytest

from magento_oaa_shared.permissions import (
    MAGENTO_ACL_PERMISSIONS,
    PERMISSION_CATEGORIES,
    get_permission_name,
    get_permission_category,
)


def test_acl_permissions_count():
    """There are exactly 34 Magento B2B ACL resources."""
    assert len(MAGENTO_ACL_PERMISSIONS) == 34


def test_all_permission_entries_are_tuples():
    for resource_id, entry in MAGENTO_ACL_PERMISSIONS.items():
        assert isinstance(entry, tuple), f"{resource_id} value is not a tuple"
        assert len(entry) == 2, f"{resource_id} tuple has wrong length"


def test_permission_categories_all_valid():
    valid_categories = set(PERMISSION_CATEGORIES.keys())
    for resource_id, (display_name, category) in MAGENTO_ACL_PERMISSIONS.items():
        assert category in valid_categories, (
            f"{resource_id} has unknown category '{category}'"
        )


def test_purchase_order_rule_namespace():
    """3 permissions use PurchaseOrderRule namespace (not PurchaseOrder)."""
    rule_perms = [
        k for k in MAGENTO_ACL_PERMISSIONS if "PurchaseOrderRule" in k
    ]
    assert len(rule_perms) == 3
    assert "Magento_PurchaseOrderRule::super_approve_purchase_order" in rule_perms
    assert "Magento_PurchaseOrderRule::view_approval_rules" in rule_perms
    assert "Magento_PurchaseOrderRule::manage_approval_rules" in rule_perms


def test_get_permission_name_known():
    assert get_permission_name("Magento_Company::index") == "All Access"
    assert get_permission_name("Magento_Sales::all") == "Sales"


def test_get_permission_name_unknown():
    assert get_permission_name("Unknown::perm") == "Unknown::perm"


def test_get_permission_category_known():
    assert get_permission_category("Magento_Company::index") == "base"
    assert get_permission_category("Magento_Sales::all") == "sales"


def test_get_permission_category_unknown():
    assert get_permission_category("Unknown::perm") == "unknown"


def test_define_oaa_permissions():
    """define_oaa_permissions adds all 34 permissions to a CustomApplication."""
    oaaclient = pytest.importorskip("oaaclient")
    from oaaclient.templates import CustomApplication
    from magento_oaa_shared.permissions import define_oaa_permissions

    app = CustomApplication(name="test", application_type="test")
    define_oaa_permissions(app)
    assert len(app.custom_permissions) == 34

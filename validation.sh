#!/usr/bin/env bash
# ============================================================
# Magento B2B Capability Check
#
# Run this on the Magento server from the Magento root directory
# to detect edition, hosting type, B2B module status, and
# GraphQL availability.
#
# Usage:
#   bash validation.sh
#   bash validation.sh /var/www/magento   # specify Magento root
# ============================================================

set -euo pipefail

MAGENTO_ROOT="${1:-.}"

if [ ! -f "$MAGENTO_ROOT/bin/magento" ]; then
    echo "ERROR: bin/magento not found in $MAGENTO_ROOT"
    echo "Usage: bash validation.sh /path/to/magento"
    exit 1
fi

cd "$MAGENTO_ROOT"

echo "========================================"
echo "  MAGENTO B2B CAPABILITY CHECK"
echo "========================================"

# --- Version ---
echo ""
echo "VERSION:"
bin/magento --version 2>/dev/null || echo "  Could not determine version"

# --- Edition ---
echo ""
echo "EDITION:"
if grep -q "enterprise" composer.json 2>/dev/null; then
    echo "  Adobe Commerce (Enterprise)"
elif grep -q "community" composer.json 2>/dev/null; then
    echo "  Magento Open Source (Community)"
else
    echo "  Unknown"
fi

# --- Hosting ---
echo ""
echo "HOSTING:"
if [ -f ".magento.app.yaml" ]; then
    echo "  Adobe Commerce Cloud"
else
    echo "  On-Premises / Self-Hosted"
fi

# --- B2B Core Module ---
echo ""
echo "B2B MODULE:"
if bin/magento module:status Magento_B2b 2>/dev/null | grep -q "enabled"; then
    echo "  Magento_B2b: ENABLED"
elif bin/magento module:status Magento_B2b 2>/dev/null | grep -q "disabled"; then
    echo "  Magento_B2b: DISABLED (installed but not enabled)"
else
    echo "  Magento_B2b: NOT INSTALLED"
fi

# --- B2B GraphQL Module ---
echo ""
echo "B2B GRAPHQL:"
if bin/magento module:status Magento_CompanyGraphQl 2>/dev/null | grep -q "enabled"; then
    echo "  Magento_CompanyGraphQl: ENABLED"
elif bin/magento module:status Magento_CompanyGraphQl 2>/dev/null | grep -q "disabled"; then
    echo "  Magento_CompanyGraphQl: DISABLED (installed but not enabled)"
else
    echo "  Magento_CompanyGraphQl: NOT INSTALLED"
fi

# --- Key B2B Modules ---
echo ""
echo "B2B MODULES:"
B2B_MODULES=(
    "Magento_Company"
    "Magento_CompanyGraphQl"
    "Magento_SharedCatalog"
    "Magento_NegotiableQuote"
    "Magento_PurchaseOrder"
    "Magento_PurchaseOrderRule"
)

FOUND=0
for MOD in "${B2B_MODULES[@]}"; do
    STATUS=$(bin/magento module:status "$MOD" 2>/dev/null || true)
    if echo "$STATUS" | grep -q "enabled"; then
        echo "  $MOD: ENABLED"
        FOUND=$((FOUND + 1))
    elif echo "$STATUS" | grep -q "disabled"; then
        echo "  $MOD: DISABLED"
        FOUND=$((FOUND + 1))
    fi
done

if [ "$FOUND" -eq 0 ]; then
    echo "  No B2B modules found"
fi

# --- GraphQL Endpoint ---
echo ""
echo "GRAPHQL ENDPOINT:"
BASE_URL=$(bin/magento config:show web/unsecure/base_url 2>/dev/null || echo "")
if [ -n "$BASE_URL" ]; then
    echo "  ${BASE_URL}graphql"
else
    echo "  Could not determine base URL"
fi

# --- Summary ---
echo ""
echo "========================================"
echo "  SUMMARY"
echo "========================================"

EDITION="unknown"
grep -q "enterprise" composer.json 2>/dev/null && EDITION="enterprise"
grep -q "community" composer.json 2>/dev/null && EDITION="community"

B2B_READY="no"
bin/magento module:status Magento_CompanyGraphQl 2>/dev/null | grep -q "enabled" && B2B_READY="yes"

if [ "$EDITION" = "community" ]; then
    echo "  Edition: Community (CE) — B2B NOT available"
    echo "  Action:  Upgrade to Adobe Commerce for B2B support"
elif [ "$B2B_READY" = "yes" ]; then
    echo "  Edition: Adobe Commerce — B2B GraphQL READY"
    echo "  Action:  Configure .env and run: python run.py"
elif [ "$EDITION" = "enterprise" ]; then
    echo "  Edition: Adobe Commerce — B2B module needs enabling"
    echo "  Action:  Run: bin/magento module:enable Magento_B2b"
else
    echo "  Could not determine readiness"
fi

echo "========================================"

#!/bin/bash
BASE="http://127.0.0.1"
RAW=$(curl -sf -X POST "$BASE/rest/V1/integration/admin/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!@#"}')
TOKEN=$(echo "$RAW" | tr -d '"')
AUTH="Authorization: Bearer $TOKEN"

# Create cart for customer 1
echo "=== Create cart ==="
CART_ID=$(curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  "$BASE/rest/V1/customers/1/carts" -d '{}')
echo "Cart: $CART_ID"
CART_CLEAN=$(echo "$CART_ID" | tr -d '"')

echo ""
echo "=== Add item (raw response) ==="
curl -v -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  "$BASE/rest/V1/carts/$CART_CLEAN/items" \
  -d "{\"cartItem\":{\"sku\":\"LAPTOP-PRO-15\",\"qty\":1,\"quote_id\":\"$CART_CLEAN\"}}" 2>&1

echo ""
echo "=== Check if product needs reindex ==="
export HOME=/root
export COMPOSER_ALLOW_SUPERUSER=1
cd /var/www/magento
php bin/magento indexer:status 2>&1

#!/bin/bash
# Create orders in Magento CE — final version
export HOME=/root
export COMPOSER_ALLOW_SUPERUSER=1

BASE="http://127.0.0.1"
log() { echo "[$(date '+%H:%M:%S')] $*"; }

RAW=$(curl -s -X POST "$BASE/rest/V1/integration/admin/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!@#"}')
TOKEN=$(echo "$RAW" | tr -d '"')
AUTH="Authorization: Bearer $TOKEN"
log "Token acquired."

create_order() {
  local email=$1 sku=$2 qty=$3

  # Get customer ID
  local cid=$(curl -s -g -H "$AUTH" \
    "$BASE/rest/V1/customers/search?searchCriteria[filter_groups][0][filters][0][field]=email&searchCriteria[filter_groups][0][filters][0][value]=$email" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

  # Create cart (ignore errors if cart exists)
  local cart=$(curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
    "$BASE/rest/V1/customers/$cid/carts" -d '{}' 2>&1 | tr -d '"')

  if [ -z "$cart" ] || echo "$cart" | grep -q "message"; then
    log "  SKIP $email — cart creation issue: $cart"
    return 0
  fi

  # Add item
  local add=$(curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
    "$BASE/rest/V1/carts/$cart/items" \
    -d "{\"cartItem\":{\"sku\":\"$sku\",\"qty\":$qty,\"quote_id\":\"$cart\"}}" 2>&1)

  if echo "$add" | grep -q "message"; then
    log "  SKIP $email — add item issue: $(echo $add | python3 -c 'import sys,json;print(json.load(sys.stdin).get(\"message\",\"\"))' 2>/dev/null)"
    return 0
  fi

  # Shipping
  curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
    "$BASE/rest/V1/carts/$cart/shipping-information" \
    -d '{
      "addressInformation": {
        "shipping_address": {
          "firstname":"Test","lastname":"Customer",
          "street":["123 Main St"],"city":"Austin",
          "region_id":57,"region_code":"TX",
          "postcode":"78701","country_id":"US",
          "telephone":"512-555-0100"
        },
        "billing_address": {
          "firstname":"Test","lastname":"Customer",
          "street":["123 Main St"],"city":"Austin",
          "region_id":57,"region_code":"TX",
          "postcode":"78701","country_id":"US",
          "telephone":"512-555-0100"
        },
        "shipping_carrier_code":"flatrate",
        "shipping_method_code":"flatrate"
      }
    }' > /dev/null 2>&1

  # Place order
  local order_id=$(curl -s -g -X PUT -H "$AUTH" -H 'Content-Type: application/json' \
    "$BASE/rest/V1/carts/$cart/order" \
    -d '{"paymentMethod":{"method":"checkmo"}}' 2>&1 | tr -d '"')

  if echo "$order_id" | grep -q "message"; then
    log "  SKIP $email — place order issue: $order_id"
    return 0
  fi

  log "  Order #$order_id: $email — $qty x $sku"
}

create_order "john.doe@example.com" "LAPTOP-PRO-15" 1
create_order "jane.smith@example.com" "PHONE-ULTRA-X" 2
create_order "bob.wilson@example.com" "SHIRT-M-BLUE" 3
create_order "alice.johnson@example.com" "PANTS-M-KHAKI" 2
create_order "charlie.brown@example.com" "JACKET-M-BLK" 1
create_order "wholesale.buyer@acmecorp.com" "LAPTOP-WORK-17" 5
create_order "procurement@techstart.io" "PHONE-PRO-MAX" 10
create_order "orders@bulkbuy.com" "LAPTOP-AIR-13" 8
create_order "store.manager@retailhub.com" "DRESS-W-RED" 20
create_order "buyer@fashionoutlet.com" "BLOUSE-W-WHT" 15

# Reindex
cd /var/www/magento
php bin/magento indexer:reindex > /dev/null 2>&1
php bin/magento cache:flush > /dev/null 2>&1

# Summary
log ""
log "=========================================="
ORDERS=$(curl -s -g -H "$AUTH" "$BASE/rest/V1/orders?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['total_count'])")
log "Total orders: $ORDERS"
log "=========================================="

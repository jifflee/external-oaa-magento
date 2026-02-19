#!/bin/bash
# Fix product website assignment and create orders
set -euo pipefail

BASE="http://127.0.0.1"
export HOME=/root
export COMPOSER_ALLOW_SUPERUSER=1

log() { echo "[$(date '+%H:%M:%S')] $*"; }

RAW=$(curl -sf -X POST "$BASE/rest/V1/integration/admin/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!@#"}')
TOKEN=$(echo "$RAW" | tr -d '"')
AUTH="Authorization: Bearer $TOKEN"
log "Token acquired."

# ---------- Assign products to website ----------
log "Assigning all products to Main Website..."
SKUS="LAPTOP-PRO-15 LAPTOP-AIR-13 LAPTOP-WORK-17 PHONE-ULTRA-X PHONE-LITE-S PHONE-PRO-MAX SHIRT-M-BLUE PANTS-M-KHAKI JACKET-M-BLK DRESS-W-RED BLOUSE-W-WHT SKIRT-W-NVY"

for SKU in $SKUS; do
  # Assign to website 1
  curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
    "$BASE/rest/V1/products/$SKU/websites" \
    -d '{"productWebsiteLink": {"sku": "'"$SKU"'", "website_id": 1}}' > /dev/null 2>&1 || true
  echo "  $SKU -> website 1"
done

# ---------- Enable shipping + payment ----------
log "Configuring shipping and payment..."
cd /var/www/magento
php bin/magento config:set carriers/flatrate/active 1 2>/dev/null
php bin/magento config:set carriers/flatrate/price 5.00 2>/dev/null
php bin/magento config:set carriers/flatrate/title "Flat Rate" 2>/dev/null
php bin/magento config:set carriers/flatrate/name "Fixed" 2>/dev/null
php bin/magento config:set payment/checkmo/active 1 2>/dev/null
php bin/magento cache:flush > /dev/null 2>&1

# ---------- Verify product is now available ----------
log "Verifying product availability..."
VERIFY=$(curl -s -g -H "$AUTH" "$BASE/rest/V1/products/LAPTOP-PRO-15" | python3 -c "
import sys, json
p = json.load(sys.stdin)
print(f'SKU={p[\"sku\"]} status={p[\"status\"]} visibility={p[\"visibility\"]}')
ea = p.get('extension_attributes', {})
stock = ea.get('stock_item', {})
print(f'in_stock={stock.get(\"is_in_stock\")} qty={stock.get(\"qty\")}')
websites = ea.get('website_ids', [])
print(f'website_ids={websites}')
" 2>&1)
echo "$VERIFY"

# ---------- Create Orders ----------
log "Creating orders..."

create_order() {
  local customer_email=$1 sku=$2 qty=$3

  CUSTOMER_ID=$(curl -sf -g -H "$AUTH" \
    "$BASE/rest/V1/customers/search?searchCriteria[filter_groups][0][filters][0][field]=email&searchCriteria[filter_groups][0][filters][0][value]=$customer_email" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

  CART_ID=$(curl -sf -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
    "$BASE/rest/V1/customers/$CUSTOMER_ID/carts" -d '{}' | tr -d '"')

  ADD_RESULT=$(curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
    "$BASE/rest/V1/carts/$CART_ID/items" \
    -d "{\"cartItem\":{\"sku\":\"$sku\",\"qty\":$qty,\"quote_id\":\"$CART_ID\"}}" 2>&1)

  # Check if add failed
  if echo "$ADD_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'item_id' in d" 2>/dev/null; then
    curl -sf -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
      "$BASE/rest/V1/carts/$CART_ID/shipping-information" \
      -d '{
        "addressInformation": {
          "shipping_address": {
            "firstname": "Test", "lastname": "Customer",
            "street": ["123 Main St"], "city": "Austin",
            "region_id": 57, "region_code": "TX",
            "postcode": "78701", "country_id": "US",
            "telephone": "512-555-0100"
          },
          "billing_address": {
            "firstname": "Test", "lastname": "Customer",
            "street": ["123 Main St"], "city": "Austin",
            "region_id": 57, "region_code": "TX",
            "postcode": "78701", "country_id": "US",
            "telephone": "512-555-0100"
          },
          "shipping_carrier_code": "flatrate",
          "shipping_method_code": "flatrate"
        }
      }' > /dev/null

    ORDER_ID=$(curl -sf -g -X PUT -H "$AUTH" -H 'Content-Type: application/json' \
      "$BASE/rest/V1/carts/$CART_ID/order" \
      -d '{"paymentMethod": {"method": "checkmo"}}' | tr -d '"')
    log "  Order #$ORDER_ID: $customer_email — $qty x $sku"
  else
    log "  FAILED add item for $customer_email: $(echo $ADD_RESULT | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"message\",\"unknown\"))' 2>/dev/null || echo 'unknown error')"
  fi
}

create_order "john.doe@example.com" "LAPTOP-PRO-15" 1
create_order "jane.smith@example.com" "PHONE-ULTRA-X" 2
create_order "bob.wilson@example.com" "SHIRT-M-BLUE" 3
create_order "wholesale.buyer@acmecorp.com" "LAPTOP-WORK-17" 5
create_order "procurement@techstart.io" "PHONE-PRO-MAX" 10
create_order "store.manager@retailhub.com" "DRESS-W-RED" 20

# ---------- Reindex ----------
log "Reindexing..."
php bin/magento indexer:reindex 2>&1 | tail -3
php bin/magento cache:flush > /dev/null

# ---------- Summary ----------
log ""
log "=========================================="
log "Final Data Summary"
log "=========================================="
curl -sf -g -H "$AUTH" "$BASE/rest/V1/customers/search?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Customers:  {json.load(sys.stdin)[\"total_count\"]}')"
curl -sf -g -H "$AUTH" "$BASE/rest/V1/products?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Products:   {json.load(sys.stdin)[\"total_count\"]}')"
curl -sf -g -H "$AUTH" "$BASE/rest/V1/orders?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Orders:     {json.load(sys.stdin)[\"total_count\"]}')"
curl -sf -g -H "$AUTH" "$BASE/rest/V1/categories" | python3 -c "
import sys, json
def count(node):
    return 1 + sum(count(c) for c in node.get('children_data', []))
print(f'Categories: {count(json.load(sys.stdin))}')
"

IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "http://169.254.169.254/latest/meta-data/public-ipv4")
log ""
log "Storefront: http://${PUBLIC_IP}/"
log "Admin:      http://${PUBLIC_IP}/admin (admin / Admin123!@#)"
log "=========================================="

#!/bin/bash
# Seed orders into Magento CE — run after seed-sample-data.sh
set -euo pipefail

BASE="http://127.0.0.1"
log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Get admin token
RAW=$(curl -sf -X POST "$BASE/rest/V1/integration/admin/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!@#"}')
TOKEN=$(echo "$RAW" | tr -d '"')
AUTH="Authorization: Bearer $TOKEN"
log "Admin token acquired."

api() {
  local method=$1 endpoint=$2
  shift 2
  curl -sf -g -X "$method" "$BASE/rest/V1/$endpoint" \
    -H 'Content-Type: application/json' \
    -H "$AUTH" \
    "$@"
}

# ---------- Update base URL to current IP ----------
log "Updating Magento base URL..."
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300" 2>/dev/null || true)
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null)
cd /var/www/magento
export HOME=/root
export COMPOSER_ALLOW_SUPERUSER=1
php bin/magento config:set web/unsecure/base_url "http://${PUBLIC_IP}/" 2>/dev/null
php bin/magento cache:flush > /dev/null 2>&1
log "Base URL updated to http://${PUBLIC_IP}/"

# ---------- Create Orders ----------
log "Creating orders..."

create_order() {
  local customer_email=$1 sku=$2 qty=$3

  # Find customer ID
  CUSTOMER_ID=$(api GET "customers/search?searchCriteria[filter_groups][0][filters][0][field]=email&searchCriteria[filter_groups][0][filters][0][value]=$customer_email" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

  # Create admin cart for customer
  CART_ID=$(api POST "customers/$CUSTOMER_ID/carts" -d '{}' | tr -d '"')

  # Add item
  api POST "carts/$CART_ID/items" -d "{
    \"cartItem\": {
      \"sku\": \"$sku\",
      \"qty\": $qty,
      \"quote_id\": \"$CART_ID\"
    }
  }" > /dev/null

  # Set shipping + billing
  api POST "carts/$CART_ID/shipping-information" -d '{
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

  # Place order
  ORDER_ID=$(api PUT "carts/$CART_ID/order" -d '{"paymentMethod": {"method": "checkmo"}}' | tr -d '"')
  log "  Order #$ORDER_ID: $customer_email — $qty x $sku"
}

create_order "john.doe@example.com" "LAPTOP-PRO-15" 1
create_order "jane.smith@example.com" "PHONE-ULTRA-X" 2
create_order "bob.wilson@example.com" "SHIRT-M-BLUE" 3
create_order "wholesale.buyer@acmecorp.com" "LAPTOP-WORK-17" 5
create_order "procurement@techstart.io" "PHONE-PRO-MAX" 10
create_order "store.manager@retailhub.com" "DRESS-W-RED" 20

log "Orders created: 6"

# ---------- Reindex ----------
log "Reindexing..."
php bin/magento indexer:reindex 2>&1 | tail -3
php bin/magento cache:flush > /dev/null

# ---------- Final Summary ----------
log ""
log "=========================================="
log "Data Summary"
log "=========================================="
api GET "customers/search?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Customers:  {json.load(sys.stdin)[\"total_count\"]}')"
api GET "products?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Products:   {json.load(sys.stdin)[\"total_count\"]}')"
api GET "orders?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Orders:     {json.load(sys.stdin)[\"total_count\"]}')"
api GET "categories" | python3 -c "
import sys, json
def count(node):
    return 1 + sum(count(c) for c in node.get('children_data', []))
print(f'Categories: {count(json.load(sys.stdin))}')
"

log ""
log "Storefront: http://${PUBLIC_IP}/"
log "Admin:      http://${PUBLIC_IP}/admin"
log "Admin user: admin / Admin123!@#"
log "=========================================="

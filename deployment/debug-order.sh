#!/bin/bash
# Debug order creation step by step

BASE="http://127.0.0.1"
RAW=$(curl -sf -X POST "$BASE/rest/V1/integration/admin/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!@#"}')
TOKEN=$(echo "$RAW" | tr -d '"')
AUTH="Authorization: Bearer $TOKEN"

echo "=== Step 1: Find customer ==="
CUSTOMER_RESULT=$(curl -s -g -H "$AUTH" "$BASE/rest/V1/customers/search?searchCriteria[filter_groups][0][filters][0][field]=email&searchCriteria[filter_groups][0][filters][0][value]=john.doe@example.com")
echo "$CUSTOMER_RESULT" | python3 -m json.tool 2>/dev/null | head -15
CUSTOMER_ID=$(echo "$CUSTOMER_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])" 2>&1)
echo "Customer ID: $CUSTOMER_ID"

echo ""
echo "=== Step 2: Check payment methods ==="
curl -s -g -H "$AUTH" "$BASE/rest/V1/store/storeConfigs" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(json.dumps(data, indent=2)[:500])
except:
    print('Failed to parse store config')
" 2>&1

echo ""
echo "=== Step 3: Check shipping methods ==="
# Enable flat rate shipping
export HOME=/root
export COMPOSER_ALLOW_SUPERUSER=1
cd /var/www/magento
php bin/magento config:set carriers/flatrate/active 1 2>&1
php bin/magento config:set carriers/flatrate/price 5.00 2>&1
php bin/magento config:set carriers/flatrate/title "Flat Rate" 2>&1
php bin/magento config:set carriers/flatrate/name "Fixed" 2>&1
echo ""

echo "=== Step 4: Enable check/money order payment ==="
php bin/magento config:set payment/checkmo/active 1 2>&1
php bin/magento cache:flush > /dev/null 2>&1
echo "Payment enabled."

echo ""
echo "=== Step 5: Create cart ==="
CART_ID=$(curl -sf -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  "$BASE/rest/V1/customers/$CUSTOMER_ID/carts" -d '{}' 2>&1)
echo "Cart ID: $CART_ID"

echo ""
echo "=== Step 6: Add item to cart ==="
CART_ID_CLEAN=$(echo "$CART_ID" | tr -d '"')
ADD_RESULT=$(curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  "$BASE/rest/V1/carts/$CART_ID_CLEAN/items" \
  -d "{\"cartItem\":{\"sku\":\"LAPTOP-PRO-15\",\"qty\":1,\"quote_id\":\"$CART_ID_CLEAN\"}}" 2>&1)
echo "$ADD_RESULT" | python3 -m json.tool 2>/dev/null | head -15

echo ""
echo "=== Step 7: Set shipping info ==="
SHIP_RESULT=$(curl -s -g -X POST -H "$AUTH" -H 'Content-Type: application/json' \
  "$BASE/rest/V1/carts/$CART_ID_CLEAN/shipping-information" \
  -d '{
    "addressInformation": {
      "shipping_address": {
        "firstname": "John", "lastname": "Doe",
        "street": ["123 Main St"], "city": "Austin",
        "region_id": 57, "region_code": "TX",
        "postcode": "78701", "country_id": "US",
        "telephone": "512-555-0100"
      },
      "billing_address": {
        "firstname": "John", "lastname": "Doe",
        "street": ["123 Main St"], "city": "Austin",
        "region_id": 57, "region_code": "TX",
        "postcode": "78701", "country_id": "US",
        "telephone": "512-555-0100"
      },
      "shipping_carrier_code": "flatrate",
      "shipping_method_code": "flatrate"
    }
  }' 2>&1)
echo "$SHIP_RESULT" | python3 -m json.tool 2>/dev/null | head -20

echo ""
echo "=== Step 8: Place order ==="
ORDER_RESULT=$(curl -s -g -X PUT -H "$AUTH" -H 'Content-Type: application/json' \
  "$BASE/rest/V1/carts/$CART_ID_CLEAN/order" \
  -d '{"paymentMethod": {"method": "checkmo"}}' 2>&1)
echo "Order result: $ORDER_RESULT"

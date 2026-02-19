#!/bin/bash
# Seed Magento CE 2.4.7 with sample data via REST API
# Run on EC2: bash seed-sample-data.sh

set -euo pipefail

BASE="http://127.0.0.1"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ---------- Admin Token ----------
log "Getting admin token..."
RAW=$(curl -sf -X POST "$BASE/rest/V1/integration/admin/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!@#"}')
TOKEN=$(echo "$RAW" | tr -d '"')
AUTH="Authorization: Bearer $TOKEN"
log "Token acquired."

api() {
  local method=$1 endpoint=$2
  shift 2
  curl -sf -X "$method" "$BASE/rest/V1/$endpoint" \
    -H 'Content-Type: application/json' \
    -H "$AUTH" \
    "$@"
}

# ---------- Categories ----------
log "Creating categories..."

# Electronics category
ELECTRONICS_ID=$(api POST categories -d '{
  "category": {
    "parent_id": 2,
    "name": "Electronics",
    "is_active": true,
    "position": 1,
    "include_in_menu": true
  }
}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
log "  Electronics: ID $ELECTRONICS_ID"

# Clothing category
CLOTHING_ID=$(api POST categories -d '{
  "category": {
    "parent_id": 2,
    "name": "Clothing",
    "is_active": true,
    "position": 2,
    "include_in_menu": true
  }
}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
log "  Clothing: ID $CLOTHING_ID"

# Subcategories
LAPTOPS_ID=$(api POST categories -d "{
  \"category\": {
    \"parent_id\": $ELECTRONICS_ID,
    \"name\": \"Laptops\",
    \"is_active\": true,
    \"position\": 1,
    \"include_in_menu\": true
  }
}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
log "  Laptops: ID $LAPTOPS_ID"

PHONES_ID=$(api POST categories -d "{
  \"category\": {
    \"parent_id\": $ELECTRONICS_ID,
    \"name\": \"Phones\",
    \"is_active\": true,
    \"position\": 2,
    \"include_in_menu\": true
  }
}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
log "  Phones: ID $PHONES_ID"

MENS_ID=$(api POST categories -d "{
  \"category\": {
    \"parent_id\": $CLOTHING_ID,
    \"name\": \"Mens\",
    \"is_active\": true,
    \"position\": 1,
    \"include_in_menu\": true
  }
}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
log "  Mens: ID $MENS_ID"

WOMENS_ID=$(api POST categories -d "{
  \"category\": {
    \"parent_id\": $CLOTHING_ID,
    \"name\": \"Womens\",
    \"is_active\": true,
    \"position\": 2,
    \"include_in_menu\": true
  }
}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
log "  Womens: ID $WOMENS_ID"

log "Categories created: 6"

# ---------- Products ----------
log "Creating products..."

create_product() {
  local sku=$1 name=$2 price=$3 cat_id=$4 qty=${5:-100}
  api POST products -d "{
    \"product\": {
      \"sku\": \"$sku\",
      \"name\": \"$name\",
      \"attribute_set_id\": 4,
      \"price\": $price,
      \"status\": 1,
      \"visibility\": 4,
      \"type_id\": \"simple\",
      \"weight\": 1.0,
      \"extension_attributes\": {
        \"category_links\": [{\"position\": 0, \"category_id\": \"$cat_id\"}],
        \"stock_item\": {\"qty\": $qty, \"is_in_stock\": true}
      }
    }
  }" > /dev/null
  echo "  - $sku: $name (\$$price)"
}

# Electronics - Laptops
create_product "LAPTOP-PRO-15" "ProBook 15 Laptop" 1299.99 "$LAPTOPS_ID" 50
create_product "LAPTOP-AIR-13" "AirLight 13 Laptop" 899.99 "$LAPTOPS_ID" 75
create_product "LAPTOP-WORK-17" "WorkStation 17 Pro" 2199.99 "$LAPTOPS_ID" 25

# Electronics - Phones
create_product "PHONE-ULTRA-X" "Ultra X Smartphone" 999.99 "$PHONES_ID" 200
create_product "PHONE-LITE-S" "Lite S Phone" 499.99 "$PHONES_ID" 300
create_product "PHONE-PRO-MAX" "Pro Max Phone" 1499.99 "$PHONES_ID" 100

# Clothing - Mens
create_product "SHIRT-M-BLUE" "Blue Oxford Shirt - Men" 59.99 "$MENS_ID" 150
create_product "PANTS-M-KHAKI" "Khaki Chinos - Men" 79.99 "$MENS_ID" 120
create_product "JACKET-M-BLK" "Black Blazer - Men" 199.99 "$MENS_ID" 60

# Clothing - Womens
create_product "DRESS-W-RED" "Red Evening Dress" 149.99 "$WOMENS_ID" 80
create_product "BLOUSE-W-WHT" "White Silk Blouse" 89.99 "$WOMENS_ID" 100
create_product "SKIRT-W-NVY" "Navy Pencil Skirt" 69.99 "$WOMENS_ID" 90

log "Products created: 12"

# ---------- Customers ----------
log "Creating customers..."

create_customer() {
  local email=$1 first=$2 last=$3 group_id=${4:-1}
  api POST customers -d "{
    \"customer\": {
      \"email\": \"$email\",
      \"firstname\": \"$first\",
      \"lastname\": \"$last\",
      \"group_id\": $group_id,
      \"store_id\": 1,
      \"website_id\": 1
    },
    \"password\": \"Test1234!@#\"
  }" > /dev/null
  echo "  - $email ($first $last, group=$group_id)"
}

# General customers (group 1)
create_customer "john.doe@example.com" "John" "Doe" 1
create_customer "jane.smith@example.com" "Jane" "Smith" 1
create_customer "bob.wilson@example.com" "Bob" "Wilson" 1
create_customer "alice.johnson@example.com" "Alice" "Johnson" 1
create_customer "charlie.brown@example.com" "Charlie" "Brown" 1

# Wholesale customers (group 2)
create_customer "wholesale.buyer@acmecorp.com" "David" "Miller" 2
create_customer "procurement@techstart.io" "Sarah" "Chen" 2
create_customer "orders@bulkbuy.com" "Michael" "Taylor" 2

# Retailer customers (group 3)
create_customer "store.manager@retailhub.com" "Emily" "Davis" 3
create_customer "buyer@fashionoutlet.com" "Robert" "Anderson" 3

log "Customers created: 10"

# ---------- Customer Addresses ----------
log "Adding customer addresses..."

add_address() {
  local customer_id=$1 first=$2 last=$3 street=$4 city=$5 state=$6 zip=$7 phone=$8
  api POST "customers/$customer_id/addresses" -d "{
    \"address\": {
      \"customer_id\": $customer_id,
      \"firstname\": \"$first\",
      \"lastname\": \"$last\",
      \"street\": [\"$street\"],
      \"city\": \"$city\",
      \"region\": {\"region\": \"$state\"},
      \"region_id\": 0,
      \"postcode\": \"$zip\",
      \"country_id\": \"US\",
      \"telephone\": \"$phone\",
      \"default_billing\": true,
      \"default_shipping\": true
    }
  }" > /dev/null 2>&1 || true
}

# Get customer IDs
CUSTOMER_IDS=$(api GET "customers/search?searchCriteria[pageSize]=10" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for c in data['items']:
    print(c['id'], c['email'])
")

# Add address to first 5 customers
echo "$CUSTOMER_IDS" | head -5 | while read id email; do
  add_address "$id" "Customer" "$id" "123 Main St" "Austin" "Texas" "78701" "512-555-0100"
  echo "  - Address added for customer $id"
done 2>/dev/null || log "  (some addresses may have failed — non-critical)"

log "Addresses added."

# ---------- Orders ----------
log "Creating orders via admin..."

create_order() {
  local customer_email=$1 sku=$2 qty=$3

  # Create cart for customer
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

  # Set shipping address
  api POST "carts/$CART_ID/shipping-information" -d '{
    "addressInformation": {
      "shipping_address": {
        "firstname": "Test",
        "lastname": "Customer",
        "street": ["123 Main St"],
        "city": "Austin",
        "region_id": 57,
        "region_code": "TX",
        "postcode": "78701",
        "country_id": "US",
        "telephone": "512-555-0100"
      },
      "billing_address": {
        "firstname": "Test",
        "lastname": "Customer",
        "street": ["123 Main St"],
        "city": "Austin",
        "region_id": 57,
        "region_code": "TX",
        "postcode": "78701",
        "country_id": "US",
        "telephone": "512-555-0100"
      },
      "shipping_carrier_code": "flatrate",
      "shipping_method_code": "flatrate"
    }
  }' > /dev/null

  # Place order
  ORDER_ID=$(api PUT "carts/$CART_ID/order" -d '{
    "paymentMethod": {"method": "checkmo"}
  }' | tr -d '"')

  echo "  - Order #$ORDER_ID: $customer_email bought $qty x $sku"
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
cd /var/www/magento
php bin/magento indexer:reindex 2>&1 | tail -3
php bin/magento cache:flush > /dev/null

# ---------- Summary ----------
log ""
log "=========================================="
log "Sample Data Seeded!"
log "=========================================="

api GET "customers/search?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Customers: {json.load(sys.stdin)[\"total_count\"]}')"
api GET "products?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Products:  {json.load(sys.stdin)[\"total_count\"]}')"
api GET "orders?searchCriteria[pageSize]=1" | python3 -c "import sys,json; print(f'Orders:    {json.load(sys.stdin)[\"total_count\"]}')"
api GET "categories" | python3 -c "
import sys, json
def count(node):
    return 1 + sum(count(c) for c in node.get('children_data', []))
print(f'Categories: {count(json.load(sys.stdin))}')
"

log ""
log "Customer passwords: Test1234!@#"
log "Admin: http://$(curl -s -H \"X-aws-ec2-metadata-token: $(curl -s -X PUT http://169.254.169.254/latest/api/token -H X-aws-ec2-metadata-token-ttl-seconds:60)\" http://169.254.169.254/latest/meta-data/public-ipv4)/admin"
log "=========================================="
